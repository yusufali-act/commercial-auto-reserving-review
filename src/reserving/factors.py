"""Development factor selection and tail fitting.

Selecting age-to-age factors is where most of the actuarial judgement in a
chain ladder sits, so this module makes the alternatives explicit:

* averaging basis: volume-weighted, simple, medial (excl. high & low)
* averaging window: all years or the latest n diagonals
* exclusions: specific (origin, age) link ratios removed with a stated reason
* tail: curve fitted to the later factors and extrapolated
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import stats

from .triangle import Triangle


# --------------------------------------------------------------------------- #
# Averages
# --------------------------------------------------------------------------- #
def average_factors(
    tri: Triangle,
    method: str = "volume",
    n_periods: int | None = None,
    exclude: set[tuple[int, int]] | None = None,
) -> pd.Series:
    """Age-to-age factors under a given averaging rule.

    Parameters
    ----------
    method : "volume" | "simple" | "medial"
    n_periods : use only the latest n link ratios in each column (None = all)
    exclude : set of (origin, starting age) link ratios to drop
    """
    v = tri.values
    lr = tri.link_ratios()
    exclude = exclude or set()
    out = {}
    for j, age in enumerate(lr.columns):
        num = v.iloc[:, j + 1]
        den = v.iloc[:, j]
        r = lr[age]
        mask = r.notna() & num.notna() & den.notna()
        for (o, a) in exclude:
            if a == age and o in mask.index:
                mask.loc[o] = False
        idx = mask[mask].index
        if n_periods is not None:
            idx = idx[-n_periods:]
        if len(idx) == 0:
            out[age] = np.nan
            continue
        if method == "volume":
            out[age] = num.loc[idx].sum() / den.loc[idx].sum()
        elif method == "simple":
            out[age] = r.loc[idx].mean()
        elif method == "medial":
            vals = r.loc[idx].sort_values()
            out[age] = vals.iloc[1:-1].mean() if len(vals) > 2 else vals.mean()
        else:
            raise ValueError(f"unknown method {method!r}")
    s = pd.Series(out, name=f"{method}{'' if n_periods is None else f' {n_periods}yr'}")
    s.index.name = "age"
    return s


def factor_comparison(tri: Triangle, exclude=None) -> pd.DataFrame:
    """Table of the usual candidate averages, one row per basis."""
    rows = []
    for method in ("volume", "simple", "medial"):
        for n in (None, 5, 3):
            rows.append(average_factors(tri, method, n, exclude))
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# Outliers
# --------------------------------------------------------------------------- #
def flag_outliers(tri: Triangle, z: float = 2.0, min_obs: int = 4) -> pd.DataFrame:
    """Flag link ratios more than `z` robust standard deviations from the column median.

    Uses median / MAD rather than mean / sd so that one extreme value does not
    hide itself by inflating the spread. Returns a boolean frame shaped like the
    link ratio triangle.
    """
    lr = tri.link_ratios()
    flags = pd.DataFrame(False, index=lr.index, columns=lr.columns)
    for age in lr.columns:
        col = lr[age].dropna()
        if len(col) < min_obs:
            continue
        med = col.median()
        mad = stats.median_abs_deviation(col, scale="normal")
        if mad == 0:
            continue
        flags.loc[col.index, age] = (col - med).abs() / mad > z
    return flags


# --------------------------------------------------------------------------- #
# Tail
# --------------------------------------------------------------------------- #
@dataclass
class TailFit:
    curve: str
    a: float
    b: float
    fit_ages: list[int]
    tail_factor: float
    r2: float
    fitted: pd.Series = field(repr=False)

    def factor_at(self, age: float) -> float:
        if self.curve == "inverse_power":
            return 1 + self.a * age ** (-self.b)
        return 1 + self.a * np.exp(-self.b * age)


def fit_tail(
    ldfs: pd.Series,
    curve: str = "inverse_power",
    fit_from: int | None = None,
    extrapolate_to: int = 50,
    cap: float = 1.25,
) -> TailFit:
    """Fit a decay curve to (f - 1) and extrapolate beyond the last observed age.

    * inverse power:  f(t) - 1 = a * t^(-b)     (Sherman, 1984) - heavier tail
    * exponential:    f(t) - 1 = a * exp(-b t)                  - lighter tail

    Fitted by OLS on log(f - 1); factors <= 1 are excluded since log(f-1) is
    undefined. The tail factor is the product of fitted factors from the last
    observed age + 1 up to `extrapolate_to`.
    """
    s = ldfs.dropna()
    if fit_from is not None:
        s = s[s.index >= fit_from]
    s = s[s > 1.0]
    if len(s) < 2:
        raise ValueError("need at least two factors > 1 to fit a tail")
    t = np.asarray(s.index, dtype=float)
    y = np.log(s.values - 1)
    x = np.log(t) if curve == "inverse_power" else t
    slope, intercept, r, *_ = stats.linregress(x, y)
    a, b = float(np.exp(intercept)), float(-slope)

    def f(age):
        return 1 + (a * age ** (-b) if curve == "inverse_power" else a * np.exp(-b * age))

    last = int(ldfs.dropna().index.max())
    tail = float(np.prod([f(k) for k in range(last + 1, extrapolate_to + 1)]))
    tail = min(tail, cap)
    fitted = pd.Series([f(k) for k in ldfs.index], index=ldfs.index)
    return TailFit(curve, a, b, [int(k) for k in s.index], tail, r**2, fitted)


# --------------------------------------------------------------------------- #
# Cumulative factors
# --------------------------------------------------------------------------- #
def cdfs(ldfs: pd.Series, tail: float = 1.0, n_ages: int | None = None) -> pd.Series:
    """Age-to-ultimate factors, indexed by age 1..n (age n -> tail only).

    `ldfs` is indexed by starting age (1..n-1). The returned series has one
    more entry: CDF at the last age equals the tail factor.
    """
    f = ldfs.astype(float).copy()
    n = n_ages or int(f.index.max()) + 1
    ages = list(range(1, n + 1))
    out = {}
    running = tail
    out[n] = running
    for age in reversed(ages[:-1]):
        running *= f.get(age, 1.0)
        out[age] = running
    s = pd.Series(out).sort_index()
    s.index.name = "age"
    return s.rename("cdf")
