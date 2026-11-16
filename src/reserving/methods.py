"""Deterministic reserving methods.

Every method returns a DataFrame indexed by origin with at least:

    latest   - observed cumulative amount on the latest diagonal
    cdf      - age-to-ultimate factor applied
    ultimate - projected ultimate

so results from different methods (and paid vs incurred bases) can be lined
up and compared directly. `summarise` converts ultimates into reserves
measured against paid to date, which is the quantity that matters for the
balance sheet regardless of whether the projection was paid- or incurred-based.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .triangle import Triangle


def _cdf_for_origins(tri: Triangle, cdf: pd.Series) -> pd.Series:
    ages = tri.latest_age()
    return ages.map(lambda a: cdf.loc[int(a)]).astype(float)


def chain_ladder(tri: Triangle, cdf: pd.Series) -> pd.DataFrame:
    latest = tri.latest_diagonal()
    f = _cdf_for_origins(tri, cdf)
    return pd.DataFrame(
        {"latest": latest, "age": tri.latest_age(), "cdf": f, "ultimate": latest * f}
    )


def expected_loss_ratio(premium: pd.Series, elr) -> pd.DataFrame:
    elr = pd.Series(elr, index=premium.index) if np.isscalar(elr) else elr.reindex(premium.index)
    return pd.DataFrame({"premium": premium, "elr": elr, "ultimate": premium * elr})


def bornhuetter_ferguson(tri: Triangle, cdf: pd.Series, prior_ultimate: pd.Series) -> pd.DataFrame:
    """BF: actual to date + expected future, with the expected *pattern* from the
    chain ladder but the expected *level* from an independent prior.

        U_BF = C + (1 - 1/CDF) * U_prior
    """
    latest = tri.latest_diagonal()
    f = _cdf_for_origins(tri, cdf)
    prior = prior_ultimate.reindex(latest.index)
    pct_unreported = 1 - 1 / f
    return pd.DataFrame(
        {
            "latest": latest,
            "age": tri.latest_age(),
            "cdf": f,
            "prior_ultimate": prior,
            "pct_unreported": pct_unreported,
            "ultimate": latest + pct_unreported * prior,
        }
    )


def cape_cod_elr(
    tri: Triangle,
    cdf: pd.Series,
    premium: pd.Series,
    decay: float = 1.0,
    lr_trend: float = 0.0,
) -> pd.Series:
    """Cape Cod (Stanard-Bühlmann) expected loss ratio, optionally generalised.

    The ELR is estimated from the triangle itself:

        ELR = sum(C_j) / sum(P_j / CDF_j)

    i.e. reported losses over 'used-up' premium. With `decay` < 1 each origin
    gets its own ELR, weighting nearby origins more heavily (decay^|i-j|).
    `lr_trend` restates every year's loss ratio to the level of the target
    year: (1 + lr_trend)^(i - j). It captures claims inflation net of rate
    change and is where a pricing/underwriting view enters.
    """
    latest = tri.latest_diagonal()
    f = _cdf_for_origins(tri, cdf)
    prem = premium.reindex(latest.index)
    used_up = prem / f
    origins = np.asarray(latest.index)
    out = {}
    for i in origins:
        w = decay ** np.abs(origins - i)
        trend = (1 + lr_trend) ** (i - origins)
        out[i] = np.sum(w * latest.values * trend) / np.sum(w * used_up.values)
    return pd.Series(out, name="cape_cod_elr")


def cape_cod(tri, cdf, premium, decay=1.0, lr_trend=0.0) -> pd.DataFrame:
    elr = cape_cod_elr(tri, cdf, premium, decay, lr_trend)
    res = bornhuetter_ferguson(tri, cdf, premium * elr)
    res.insert(3, "elr", elr)
    return res


def benktander(tri: Triangle, cdf: pd.Series, prior_ultimate: pd.Series, iterations: int = 1) -> pd.DataFrame:
    """Benktander-Hovinen: BF applied again, using the BF ultimate as the prior.

    Credibility-weighted between BF and CL with weight on CL equal to the % reported.
    One iteration is the standard version; infinitely many converge to CL.
    """
    u = prior_ultimate
    for _ in range(iterations + 1):
        res = bornhuetter_ferguson(tri, cdf, u)
        u = res["ultimate"]
    res["prior_ultimate"] = prior_ultimate.reindex(res.index)
    return res


def summarise(results: dict[str, pd.DataFrame], paid_latest: pd.Series, incurred_latest: pd.Series | None = None) -> pd.DataFrame:
    """Line up ultimates from several methods and convert them to unpaid amounts.

    unpaid  = ultimate - paid to date   (case reserves + IBNR)
    ibnr    = ultimate - case incurred  (only if incurred_latest supplied)
    """
    ult = pd.DataFrame({k: v["ultimate"] for k, v in results.items()})
    unpaid = ult.sub(paid_latest, axis=0)
    out = {"ultimate": ult, "unpaid": unpaid}
    if incurred_latest is not None:
        out["ibnr"] = ult.sub(incurred_latest, axis=0)
    return pd.concat(out, axis=1)
