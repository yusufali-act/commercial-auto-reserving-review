"""Turning several method results into one selected reserve.

The selection is made by accident-year maturity band, because which method is
most reliable depends on how developed the year is:

* immature years: little data, CL is highly leveraged -> lean on prior-based
  methods (BF / Cape Cod)
* mature years: the data speaks for itself -> lean on development methods

Weights within each band start from back-test evidence (inverse mean squared
error, estimated on one half of the companies and checked on the other half)
and are then adjusted for company-specific diagnostics.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

BANDS = {"1-2 (immature)": (1, 2), "3-5 (developing)": (3, 5), "6-10 (mature)": (6, 10)}


def band_of(age: int) -> str:
    for name, (lo, hi) in BANDS.items():
        if lo <= age <= hi:
            return name
    raise ValueError(age)


def band_weights(bt: pd.DataFrame, methods: list[str]) -> pd.DataFrame:
    """Inverse-MSE weights per maturity band (rows) and method (columns)."""
    b = bt[bt["method"].isin(methods)].assign(band=lambda d: d["age"].map(band_of))
    mse = b.groupby(["band", "method"])["error_pct_premium"].apply(lambda x: np.mean(x**2)).unstack()[methods]
    w = 1 / mse
    return w.div(w.sum(axis=1), axis=0).loc[list(BANDS)]


def blend(ultimates: pd.DataFrame, ages: pd.Series, weights: pd.DataFrame) -> pd.Series:
    """Weighted ultimate per origin, weights chosen by the origin's maturity band."""
    out = {}
    for o in ultimates.index:
        w = weights.loc[band_of(int(ages[o]))]
        out[o] = float((ultimates.loc[o, w.index] * w).sum())
    return pd.Series(out, name="selected")


def train_test_evaluation(bt: pd.DataFrame, methods: list[str], seed: int = 0, n_splits: int = 50) -> pd.DataFrame:
    """Out-of-sample check of the blended selection.

    Repeatedly split companies in half; learn band weights on one half, apply
    them to the other half, and compare RMSE (as % of premium) with each
    single method on the same held-out companies.
    """
    rng = np.random.default_rng(seed)
    companies = bt["grcode"].unique()
    results = []
    for s in range(n_splits):
        train = rng.choice(companies, size=len(companies) // 2, replace=False)
        tr, te = bt[bt["grcode"].isin(train)], bt[~bt["grcode"].isin(train)]
        w = band_weights(tr, methods)
        wide = te.pivot_table(index=["grcode", "origin"], columns="method", values="estimate_ult")
        meta = te.drop_duplicates(["grcode", "origin"]).set_index(["grcode", "origin"])[["age", "actual_ult", "premium"]]
        wide = wide.join(meta)
        wide["Blended"] = [
            float((wide.loc[i, methods] * w.loc[band_of(int(wide.loc[i, "age"]))]).sum()) for i in wide.index
        ]
        for m in methods + ["Blended"]:
            err = (wide[m] - wide["actual_ult"]) / wide["premium"]
            results.append({"split": s, "method": m, "rmse": np.sqrt(np.mean(err**2)), "bias": err.mean()})
    r = pd.DataFrame(results)
    return r.groupby("method")[["rmse", "bias"]].mean().sort_values("rmse")
