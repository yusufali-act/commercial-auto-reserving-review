"""Diagnostics that test the chain ladder's assumptions before trusting it.

The chain ladder assumes each origin year develops like the average of the
past. The checks here look for evidence that this is not true:

* paid / case-incurred ratios moving along diagonals -> a change in
  settlement speed or in case reserve strength (Berquist & Sherman, 1977)
* Pearson residuals from the ODP chain ladder trending by calendar year ->
  calendar-year (inflation-type) effects the model does not capture
* implied loss ratios drifting by accident year -> the a-priori for BF must
  reflect that drift
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .factors import average_factors
from .triangle import Triangle


def ratio_triangle(num: Triangle, den: Triangle) -> pd.DataFrame:
    return (num.values / den.values).where(num.values.notna() & den.values.notna())


def diagonal_shift(ratio: pd.DataFrame, base_origins: int = 5) -> pd.Series:
    """Average change in a ratio triangle by calendar year, relative to its age average.

    Each cell is divided by the average for its age over the `base_origins`
    oldest origin years; the result is averaged along each diagonal. A value
    trending away from 1.0 says the ratio is moving through time, not by age.
    """
    base = ratio.iloc[:base_origins].mean()
    rel = ratio / base
    cal = Triangle(ratio).calendar_period()
    df = pd.DataFrame({"rel": rel.stack(), "cal": cal.where(ratio.notna()).stack()}).dropna()
    return df.groupby("cal")["rel"].mean().rename("relative_to_base")


def outlier_list(flags: pd.DataFrame, values: pd.DataFrame | None = None) -> pd.DataFrame:
    rows = [(o, a) for o in flags.index for a in flags.columns if bool(flags.loc[o, a])]
    out = pd.DataFrame(rows, columns=["origin", "age"])
    if values is not None and len(out):
        out["link_ratio"] = [values.loc[o, a] for o, a in rows]
        out["age_median"] = [values[a].median() for _, a in rows]
    return out


def pearson_residuals(tri: Triangle) -> pd.DataFrame:
    """Unscaled Pearson residuals of incremental amounts under the ODP chain ladder.

    Expected incrementals are back-fitted from the latest diagonal using
    volume-weighted factors (equivalent to the ODP GLM fit).
    """
    C = tri.values
    f = average_factors(tri)
    fitted = pd.DataFrame(np.nan, index=C.index, columns=C.columns)
    for o in C.index:
        row = C.loc[o].dropna()
        a = int(row.index[-1])
        fitted.loc[o, a] = row.iloc[-1]
        for k in range(a - 1, 0, -1):
            fitted.loc[o, k] = fitted.loc[o, k + 1] / f.loc[k]
    m = fitted.diff(axis=1)
    m.iloc[:, 0] = fitted.iloc[:, 0]
    x = tri.incremental()
    return (x - m) / np.sqrt(m.abs())


def residuals_by(res: pd.DataFrame, by: str) -> pd.DataFrame:
    """Mean residual by origin, development age or calendar year."""
    cal = Triangle(res).calendar_period()
    long = pd.DataFrame(
        {
            "resid": res.stack(),
            "origin": res.stack().index.get_level_values(0),
            "age": res.stack().index.get_level_values(1),
            "calendar": cal.where(res.notna()).stack().values,
        }
    ).dropna()
    return long.groupby(by)["resid"].agg(["mean", "count"])


def implied_loss_ratios(ultimates: pd.DataFrame, premium: pd.Series) -> pd.DataFrame:
    return ultimates.div(premium, axis=0)


# --------------------------------------------------------------------------- #
# Claim-level diagnostics (SPLICE)
# --------------------------------------------------------------------------- #
def average_case_reserve(snap: pd.DataFrame, max_dev: int = 10) -> pd.DataFrame:
    """Average case reserve per open claim - the check behind Berquist-Sherman case adjustments."""
    s = snap[(snap["dev"] <= max_dev) & snap["observed"]]
    open_ = s[s["reported"] & ~s["closed"]]
    g = open_.groupby(["ay", "dev"]).agg(os=("case_os", "sum"), n=("claim_no", "size"))
    return (g["os"] / g["n"]).unstack()


def closure_rate(closed: Triangle, reported: Triangle) -> pd.DataFrame:
    """Closed / reported counts - the settlement-speed check behind Berquist-Sherman paid adjustments."""
    return ratio_triangle(closed, reported)
