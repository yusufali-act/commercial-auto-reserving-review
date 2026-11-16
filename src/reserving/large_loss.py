"""Claim-level adjustments: inflation and large losses.

The chain ladder implicitly assumes that whatever inflation is embedded in the
historical development will continue. When inflation changes - as it did for
motor claims from 2022 - that assumption fails. The standard fix is to:

1. restate past incremental payments into constant money using a claims
   inflation index (by calendar year of payment);
2. project in real terms, where the development pattern should be stable;
3. re-inflate future payments to the calendar year they will be paid in,
   using an explicit assumption for future inflation.

Large losses distort link ratios (one big claim in one cell moves the factor
for every origin year). The standard fix is to cap each claim at a threshold,
develop the capped ("attritional") triangle, and load for the excess using a
frequency x severity approach that pools experience across years.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .factors import average_factors, cdfs
from .methods import cape_cod_elr
from .triangle import Triangle


# --------------------------------------------------------------------------- #
# Inflation
# --------------------------------------------------------------------------- #
def inflation_index(rates: pd.Series | dict, base_year: int) -> pd.Series:
    """Cumulative index from annual inflation rates (rate for year y applies from y-1 to y).

    Normalised to 1.0 at `base_year`.
    """
    r = pd.Series(rates).sort_index()
    idx = (1 + r).cumprod()
    idx = idx / idx.loc[base_year]
    return idx


def to_real_terms(tri: Triangle, index: pd.Series) -> Triangle:
    """Restate a cumulative triangle into money of the index base year.

    Each incremental payment is divided by the index for the calendar year in
    which it was paid, then the triangle is re-cumulated.
    """
    inc = tri.incremental()
    cal = tri.calendar_period()
    deflator = cal.apply(lambda col: col.map(index))
    real = (inc / deflator).where(inc.notna())
    return Triangle.from_incremental(real, name=f"{tri.name} (real)")


def project_nominal(
    real_tri: Triangle,
    ldfs: pd.Series,
    valuation_year: int,
    future_inflation: float,
    tail: float = 1.0,
) -> pd.DataFrame:
    """Chain ladder in real terms, with future cash flows re-inflated.

    Returns per origin: real latest, real ultimate, and the nominal unpaid
    amount once each future year's payment is inflated at `future_inflation`
    p.a. from the valuation year.
    """
    n = int(real_tri.ages.max())
    rows = {}
    for o in real_tri.origins:
        age = int(real_tri.latest_age()[o])
        cum = real_tri.latest_diagonal()[o]
        unpaid_real = unpaid_nom = 0.0
        for k in range(age, n):
            nxt = cum * ldfs.get(k, 1.0)
            cal = o + k  # calendar year of development age k+1
            unpaid_real += nxt - cum
            unpaid_nom += (nxt - cum) * (1 + future_inflation) ** (cal - valuation_year)
            cum = nxt
        if tail != 1.0:
            extra = cum * (tail - 1)
            unpaid_real += extra
            unpaid_nom += extra * (1 + future_inflation) ** (o + n - valuation_year)
        rows[o] = {"latest_real": real_tri.latest_diagonal()[o], "unpaid_real": unpaid_real, "unpaid": unpaid_nom}
    return pd.DataFrame(rows).T


def inflation_adjusted_cape_cod(
    real_tri: Triangle,
    ldfs: pd.Series,
    exposure: pd.Series,
    valuation_year: int,
    future_inflation: float,
    decay: float = 1.0,
) -> pd.DataFrame:
    """Cape Cod in real terms: expected real cost per unit of exposure is pooled
    across years (stable once inflation is removed), then BF-style future
    payments are re-inflated. Much less leveraged than CL for immature years.
    """
    c = cdfs(ldfs)
    elr = cape_cod_elr(real_tri, c, exposure, decay=decay)
    prior = exposure * elr
    pattern = 1 / c  # % paid by age
    n = int(real_tri.ages.max())
    rows = {}
    for o in real_tri.origins:
        age = int(real_tri.latest_age()[o])
        unpaid_real = unpaid_nom = 0.0
        for k in range(age, n):
            inc_pct = pattern.loc[k + 1] - pattern.loc[k]
            fut = prior[o] * inc_pct
            unpaid_real += fut
            unpaid_nom += fut * (1 + future_inflation) ** (o + k - valuation_year)
        rows[o] = {"prior_real": prior[o], "cost_per_exposure_real": elr[o], "unpaid_real": unpaid_real, "unpaid": unpaid_nom}
    return pd.DataFrame(rows).T


def payment_inflation_index(txns: pd.DataFrame, first_year: int, valuation_year: int, min_payments: int = 30) -> pd.DataFrame:
    """Estimate claims inflation by calendar year from average payment sizes.

    Geometric-mean payment per payment is computed for every accident year x
    development age cell. Comparing the same development age in successive
    accident years isolates the change from one calendar year to the next
    (the mix of claims at a given age is similar each year). The log changes
    are averaged across ages, weighted by payment counts, and chained into an
    index. This uses only data a reserving team actually has: payment
    amounts and dates.
    """
    t = txns.copy()
    t["pay"] = t.groupby("claim_no")["cumpaid"].diff().fillna(t["cumpaid"]).clip(lower=0)
    t = t[t["pay"] > 0]
    t["cal"] = first_year + ((t["txn_time"] - 1e-9) // 4).astype(int)
    t = t[t["cal"] <= valuation_year]
    t["dev"] = t["cal"] - t["ay"] + 1
    # geometric mean payment: robust to the handful of very large payments that
    # dominate an arithmetic average in a heavy-tailed book
    t["logpay"] = np.log(t["pay"])
    cells = t.groupby(["ay", "dev"]).agg(n=("pay", "size"), avg=("logpay", "mean")).reset_index()
    cells["avg"] = np.exp(cells["avg"])
    cells = cells[cells["n"] >= min_payments]
    avg = cells.pivot(index="ay", columns="dev", values="avg")
    n = cells.pivot(index="ay", columns="dev", values="n")
    rows = []
    for ay in avg.index[1:]:
        for dev in avg.columns:
            a1, a0 = avg.loc[ay, dev], avg.loc[ay - 1, dev] if ay - 1 in avg.index else np.nan
            if np.isfinite(a1) and np.isfinite(a0):
                rows.append({"cal": ay + dev - 1, "dlog": np.log(a1 / a0), "w": min(n.loc[ay, dev], n.loc[ay - 1, dev])})
    d = pd.DataFrame(rows)
    by_cal = d.groupby("cal").apply(lambda g: pd.Series({"inflation": np.exp(np.average(g["dlog"], weights=g["w"])) - 1,
                                                         "cells": len(g), "payments": g["w"].sum()}))
    by_cal["index"] = (1 + by_cal["inflation"]).cumprod()
    return by_cal


# --------------------------------------------------------------------------- #
# Large losses
# --------------------------------------------------------------------------- #
def capped_triangles(snap: pd.DataFrame, threshold: float, index: pd.Series | None = None, max_dev: int = 10, value: str = "incurred") -> dict[str, Triangle]:
    """Split claim-level amounts into attritional (capped) and excess parts.

    The threshold is in base-year money and, if an index is given, moves with
    inflation by accident year, so that 'large' means the same in real terms
    across years (otherwise inflation alone pushes more claims over a fixed cap
    and the excess triangle develops spuriously).
    """
    s = snap[(snap["dev"] <= max_dev)].copy()
    thr = threshold * (s["ay"].map(index) if index is not None else 1.0)
    s["capped"] = np.minimum(s[value], thr)
    s["excess"] = (s[value] - s["capped"]).clip(lower=0)
    s["is_large"] = s[value] > thr
    agg = s.groupby(["ay", "dev"]).agg(capped=("capped", "sum"), excess=("excess", "sum"), large_count=("is_large", "sum")).reset_index()
    return {k: Triangle.from_long(agg, "ay", "dev", k, name=k) for k in ["capped", "excess", "large_count"]}


def large_loss_load(
    large_count: Triangle,
    excess: Triangle,
    exposure: pd.Series,
    index: pd.Series,
) -> pd.DataFrame:
    """Frequency x severity load for the excess layer, pooled across years.

    * frequency: ultimate large-claim counts from a count chain ladder; the
      large frequency per exposure is then pooled (Cape Cod style) so that the
      latest years are not driven by one or two reported large claims;
    * severity: average excess per large claim on mature years, in real terms,
      re-indexed to each accident year.
    """
    c_cnt = cdfs(average_factors(large_count))
    freq = cape_cod_elr(large_count, c_cnt, exposure)            # large claims per exposure (pooled)
    exp_count = exposure * freq
    lat_cnt = large_count.latest_diagonal()
    ult_cnt = lat_cnt + (1 - 1 / large_count.latest_age().map(c_cnt)) * exp_count

    c_xs = cdfs(average_factors(excess))
    xs_ult_cl = excess.latest_diagonal() * excess.latest_age().map(c_xs)
    real_sev = (xs_ult_cl / index.reindex(xs_ult_cl.index)) / ult_cnt.where(ult_cnt > 0)
    mature = large_count.latest_age() >= 5
    sev_real = (xs_ult_cl[mature] / index.reindex(xs_ult_cl.index)[mature]).sum() / ult_cnt[mature].sum()

    exp_xs = ult_cnt * sev_real * index.reindex(ult_cnt.index)
    # BF on the excess layer using the frequency-severity prior
    pct_unrep = 1 - 1 / excess.latest_age().map(c_xs)
    ult_xs = excess.latest_diagonal() + pct_unrep * exp_xs
    return pd.DataFrame(
        {
            "large_reported": lat_cnt,
            "large_ultimate_count": ult_cnt,
            "severity_real": sev_real,
            "observed_real_severity": real_sev,
            "excess_reported": excess.latest_diagonal(),
            "excess_prior": exp_xs,
            "excess_ultimate": ult_xs,
        }
    )
