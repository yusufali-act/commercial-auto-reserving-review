"""Reserve uncertainty: Mack (1993) analytic standard errors and the
England & Verrall (2002) over-dispersed Poisson bootstrap.

Both are tied to the volume-weighted chain ladder, so they measure the
uncertainty *of that model*. They do not capture model error (e.g. the risk
that the chain ladder is the wrong model because settlement has sped up),
which is why the report treats their output as a lower bound on true
uncertainty.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats

from .triangle import Triangle


# --------------------------------------------------------------------------- #
# Mack
# --------------------------------------------------------------------------- #
@dataclass
class MackResult:
    table: pd.DataFrame       # per origin: latest, ultimate, reserve, process/parameter/total s.e., cv
    total_reserve: float
    total_se: float
    factors: pd.Series
    sigma2: pd.Series

    @property
    def total_cv(self) -> float:
        return self.total_se / self.total_reserve

    def lognormal_percentile(self, q: float) -> float:
        """Reserve percentile assuming a lognormal with the Mack mean and s.e."""
        m, s = self.total_reserve, self.total_se
        sigma2 = np.log(1 + (s / m) ** 2)
        mu = np.log(m) - sigma2 / 2
        return float(np.exp(mu + np.sqrt(sigma2) * stats.norm.ppf(q)))


def mack(tri: Triangle) -> MackResult:
    C = tri.values.to_numpy(dtype=float)
    n, m = C.shape
    latest_idx = np.array([np.max(np.where(~np.isnan(r))[0]) for r in C])

    f = np.ones(m - 1)
    s2 = np.full(m - 1, np.nan)
    S = np.zeros(m - 1)
    for k in range(m - 1):
        rows = ~np.isnan(C[:, k + 1]) & ~np.isnan(C[:, k])
        S[k] = C[rows, k].sum()
        f[k] = C[rows, k + 1].sum() / S[k]
        if rows.sum() > 1:
            ratio = C[rows, k + 1] / C[rows, k]
            s2[k] = np.sum(C[rows, k] * (ratio - f[k]) ** 2) / (rows.sum() - 1)
    # Mack's extrapolation for the final sigma^2 (only one link ratio observed)
    if np.isnan(s2[-1]) and m >= 4:
        s2[-1] = min(s2[-2] ** 2 / s2[-3], s2[-3], s2[-2])

    # Project
    Chat = C.copy()
    for i in range(n):
        for k in range(latest_idx[i], m - 1):
            Chat[i, k + 1] = Chat[i, k] * f[k]
    U = Chat[:, -1]
    latest = C[np.arange(n), latest_idx]
    R = U - latest

    proc = np.zeros(n)
    param = np.zeros(n)
    for i in range(n):
        for k in range(latest_idx[i], m - 1):
            proc[i] += s2[k] / f[k] ** 2 / Chat[i, k]
            param[i] += s2[k] / f[k] ** 2 / S[k]
    proc_var = U**2 * proc
    param_var = U**2 * param
    mse = proc_var + param_var

    # Covariance between origins (shared parameter error)
    cross = 0.0
    for i in range(n):
        for j in range(n):
            if latest_idx[j] < latest_idx[i]:  # j is less developed than i
                ks = range(latest_idx[i], m - 1)
                cross += U[i] * U[j] * sum(2 * s2[k] / f[k] ** 2 / S[k] for k in ks)
    total_mse = mse.sum() + cross

    table = pd.DataFrame(
        {
            "latest": latest,
            "ultimate": U,
            "reserve": R,
            "process_se": np.sqrt(proc_var),
            "parameter_se": np.sqrt(param_var),
            "mack_se": np.sqrt(mse),
        },
        index=tri.origins,
    )
    table["cv"] = table["mack_se"] / table["reserve"].where(table["reserve"].abs() > 1e-9)
    ages = tri.ages[:-1]
    return MackResult(
        table=table,
        total_reserve=float(R.sum()),
        total_se=float(np.sqrt(total_mse)),
        factors=pd.Series(f, index=ages),
        sigma2=pd.Series(s2, index=ages),
    )


# --------------------------------------------------------------------------- #
# ODP bootstrap
# --------------------------------------------------------------------------- #
@dataclass
class BootstrapResult:
    reserves: np.ndarray          # (n_sims, n_origins) simulated reserves incl. process error
    origins: pd.Index
    phi: float
    residuals: np.ndarray
    point_reserve: pd.Series      # deterministic CL reserve

    @property
    def total(self) -> np.ndarray:
        return self.reserves.sum(axis=1)

    def summary(self, qs=(0.5, 0.75, 0.9, 0.95, 0.995)) -> pd.DataFrame:
        df = pd.DataFrame(self.reserves, columns=self.origins)
        df["Total"] = self.total
        out = pd.DataFrame({"cl_reserve": list(self.point_reserve) + [self.point_reserve.sum()],
                            "mean": df.mean(), "se": df.std(ddof=1)}, index=df.columns)
        out["cv"] = out["se"] / out["mean"]
        for q in qs:
            out[f"p{q*100:g}"] = df.quantile(q)
        return out


def _vol_factors(cum: np.ndarray) -> np.ndarray:
    """Volume-weighted factors for a stack of triangles (S, n, m)."""
    m = cum.shape[-1]
    f = np.ones(cum.shape[:-2] + (m - 1,))
    for k in range(m - 1):
        rows = ~np.isnan(cum[..., :, k + 1])
        num = np.where(rows, cum[..., :, k + 1], 0).sum(axis=-1)
        den = np.where(rows, cum[..., :, k], 0).sum(axis=-1)
        f[..., k] = num / den
    return f


def odp_bootstrap(tri: Triangle, n_sims: int = 10_000, seed: int = 0, process: bool = True) -> BootstrapResult:
    """England & Verrall (2002) bootstrap of the over-dispersed Poisson chain ladder.

    1. Fit the volume-weighted chain ladder and back-fit expected incrementals m.
    2. Unscaled Pearson residuals r = (X - m) / sqrt(m); scale phi = sum r^2 / (N - p).
    3. Resample bias-adjusted residuals -> pseudo triangles -> refit CL (parameter error).
    4. Simulate future incrementals from a gamma with mean m and variance phi*m (process error).
    """
    rng = np.random.default_rng(seed)
    C = tri.values.to_numpy(dtype=float)
    n, m = C.shape
    obs = ~np.isnan(C)
    latest_idx = np.array([np.max(np.where(r)[0]) for r in obs])

    f = _vol_factors(C[None])[0]
    # back-fit expected cumulatives from the latest diagonal
    Cfit = np.full_like(C, np.nan)
    for i in range(n):
        Cfit[i, latest_idx[i]] = C[i, latest_idx[i]]
        for k in range(latest_idx[i] - 1, -1, -1):
            Cfit[i, k] = Cfit[i, k + 1] / f[k]
    mfit = np.diff(np.concatenate([np.zeros((n, 1)), Cfit], axis=1), axis=1)
    X = np.diff(np.concatenate([np.zeros((n, 1)), C], axis=1), axis=1)

    resid = (X - mfit) / np.sqrt(np.abs(mfit))
    N = obs.sum()
    p = n + m - 1
    phi = np.nansum(resid**2) / (N - p)
    adj = resid * np.sqrt(N / (N - p))
    pool = adj[obs]
    pool = pool[np.abs(pool) > 1e-12]  # drop the structurally-zero corner residuals

    # pseudo incrementals for all sims at once
    draws = rng.choice(pool, size=(n_sims, n, m))
    Xstar = mfit[None] + draws * np.sqrt(np.abs(mfit))[None]
    Xstar = np.where(obs[None], Xstar, np.nan)
    Cstar = np.cumsum(np.nan_to_num(Xstar), axis=2)
    Cstar = np.where(obs[None], Cstar, np.nan)
    fstar = _vol_factors(Cstar)  # (S, m-1)

    reserves = np.zeros((n_sims, n))
    for i in range(n):
        a = latest_idx[i]
        if a == m - 1:
            continue
        c = Cstar[:, i, a]
        prev = c
        total = np.zeros(n_sims)
        for k in range(a, m - 1):
            nxt = prev * fstar[:, k]
            mu = nxt - prev
            if process:
                shape = np.abs(mu) / phi
                sim = rng.gamma(np.maximum(shape, 1e-12), phi) * np.sign(mu)
            else:
                sim = mu
            total += sim
            prev = nxt
        reserves[:, i] = total

    # deterministic CL reserve for reference
    proj = C.copy()
    for i in range(n):
        for k in range(latest_idx[i], m - 1):
            proj[i, k + 1] = proj[i, k] * f[k]
    point = pd.Series(proj[:, -1] - C[np.arange(n), latest_idx], index=tri.origins)
    return BootstrapResult(reserves, tri.origins, float(phi), adj, point)
