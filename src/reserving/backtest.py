"""Back-testing: how would each method have performed?

Two tests, both using the hindsight in the CAS full square:

1. Rolling test for the study company - re-run each method as at 1994, 1995,
   1996 and 1997 using only data available then, and compare the reserve
   with what was actually paid/incurred afterwards.

2. Cross-company test - run a fixed, judgement-free version of each method on
   every clean company as at 1997 and measure the error by accident-year
   maturity. This gives evidence on *which method to trust at which age*,
   playing the role that a company's own actual-vs-expected history and
   industry studies play in practice.

Methods are applied mechanically here (all-year volume-weighted factors, rule
based tails and priors) - the point is to compare methods, not to reproduce
the judgement in the main analysis.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import data as D
from .factors import average_factors, cdfs, fit_tail
from .methods import benktander, bornhuetter_ferguson, cape_cod, cape_cod_elr, chain_ladder
from .triangle import Triangle

METHODS = [
    "CL paid",
    "CL case",
    "BF paid",
    "BF case",
    "Cape Cod paid",
    "Cape Cod case",
    "Gen. Cape Cod case",
    "Benktander case",
    "ELR",
]


def _tail(ldfs: pd.Series, full_age: int, default: float) -> float:
    """Default tail once the triangle reaches `full_age`; otherwise a fitted curve."""
    if int(ldfs.index.max()) + 1 >= full_age:
        return default
    try:
        t = fit_tail(ldfs, "inverse_power", fit_from=2, extrapolate_to=full_age + 10)
        return t.tail_factor
    except ValueError:
        return default


def industry_prior_lr(ind_case: Triangle, ind_premium: pd.Series, tail: float = 1.002) -> pd.Series:
    c = cdfs(average_factors(ind_case), tail)
    return chain_ladder(ind_case, c)["ultimate"] / ind_premium.reindex(ind_case.origins)


def standard_methods(
    paid: Triangle,
    case: Triangle,
    premium: pd.Series,
    prior_lr: pd.Series,
    tail_paid: float = 1.005,
    tail_case: float = 1.002,
    full_age: int = 10,
) -> pd.DataFrame:
    """Ultimates from each method (rows = origin, cols = method)."""
    prem = premium.reindex(paid.origins)
    fp, fc = average_factors(paid), average_factors(case)
    tp, tc = _tail(fp, full_age, tail_paid), _tail(fc, full_age, tail_case)
    cP, cC = cdfs(fp, tp), cdfs(fc, tc)

    # Prior: industry loss ratio for each year, scaled by the company's own
    # relativity to industry on its most mature years (where its CL is reliable).
    cl_case = chain_ladder(case, cC)["ultimate"]
    mature = case.latest_age() >= max(3, int(case.latest_age().max()) - 4)
    ind_lr = prior_lr.reindex(paid.origins)
    company_lr_mature = cl_case[mature].sum() / prem[mature].sum()
    industry_lr_mature = (ind_lr[mature] * prem[mature]).sum() / prem[mature].sum()
    prior = prem * ind_lr * (company_lr_mature / industry_lr_mature)
    cc_elr = cape_cod_elr(case, cC, prem)

    out = {
        "CL paid": chain_ladder(paid, cP)["ultimate"],
        "CL case": cl_case,
        "BF paid": bornhuetter_ferguson(paid, cP, prior)["ultimate"],
        "BF case": bornhuetter_ferguson(case, cC, prior)["ultimate"],
        "Cape Cod paid": cape_cod(paid, cP, prem)["ultimate"],
        "Cape Cod case": cape_cod(case, cC, prem)["ultimate"],
        "Gen. Cape Cod case": cape_cod(case, cC, prem, decay=0.75)["ultimate"],
        "Benktander case": benktander(case, cC, prem * cc_elr)["ultimate"],
        "ELR": prior,
    }
    return pd.DataFrame(out)


def rolling_backtest(co: D.CompanyData, ind: D.CompanyData, valuations=(1994, 1995, 1996, 1997)) -> pd.DataFrame:
    """Total unpaid estimate by method at each valuation vs the actual outcome."""
    rows = []
    actual_ult = co.actual_ultimate
    for v in valuations:
        paid, case = co.paid_full.as_at(v), co.case_full.as_at(v)
        prior = industry_prior_lr(ind.case_full.as_at(v), ind.premium)
        ult = standard_methods(paid, case, co.premium, prior)
        paid_latest = paid.latest_diagonal()
        actual_unpaid = (actual_ult.reindex(paid.origins) - paid_latest).sum()
        for m in ult.columns:
            est = (ult[m] - paid_latest).sum()
            rows.append({"valuation": v, "method": m, "estimate": est, "actual": actual_unpaid, "error_pct": est / actual_unpaid - 1})
    return pd.DataFrame(rows)


def cross_company_backtest(df: pd.DataFrame, grcodes: list[int], valuation: int = 1997) -> pd.DataFrame:
    """Long table: company x origin x method with estimated and actual ultimates."""
    rows = []
    for g in grcodes:
        co = D.company(df, g)
        ind = D.industry(df, exclude=g, grcodes=grcodes)
        paid, case = co.paid_full.as_at(valuation), co.case_full.as_at(valuation)
        prior = industry_prior_lr(ind.case_full.as_at(valuation), ind.premium)
        ult = standard_methods(paid, case, co.premium, prior)
        actual = co.actual_ultimate.reindex(paid.origins)
        paid_latest = paid.latest_diagonal()
        age = paid.latest_age()
        for m in ult.columns:
            for o in paid.origins:
                rows.append(
                    {
                        "grcode": g,
                        "company": co.name,
                        "origin": o,
                        "age": int(age[o]),
                        "method": m,
                        "premium": co.premium[o],
                        "estimate_ult": ult.loc[o, m],
                        "actual_ult": actual[o],
                        "paid_latest": paid_latest[o],
                    }
                )
    bt = pd.DataFrame(rows)
    bt["error_pct_premium"] = (bt["estimate_ult"] - bt["actual_ult"]) / bt["premium"]
    return bt


def error_by_age(bt: pd.DataFrame) -> pd.DataFrame:
    """Bias (mean error) and RMSE as a % of premium, by maturity and method."""
    g = bt.groupby(["age", "method"])["error_pct_premium"]
    out = pd.DataFrame({"bias": g.mean(), "rmse": g.apply(lambda x: np.sqrt(np.mean(x**2))), "mae": g.apply(lambda x: x.abs().mean())})
    return out.reset_index()


def company_total_errors(bt: pd.DataFrame) -> pd.DataFrame:
    """Total reserve error per company and method, as % of actual unpaid."""
    bt = bt.assign(est_unpaid=bt["estimate_ult"] - bt["paid_latest"], act_unpaid=bt["actual_ult"] - bt["paid_latest"])
    tot = bt.groupby(["grcode", "company", "method"])[["est_unpaid", "act_unpaid"]].sum()
    tot["error_pct"] = tot["est_unpaid"] / tot["act_unpaid"] - 1
    return tot.reset_index()


def inverse_mse_weights(err: pd.DataFrame, methods: list[str]) -> pd.DataFrame:
    """Evidence-based method weights by age: proportional to 1 / MSE."""
    e = err[err["method"].isin(methods)].pivot(index="age", columns="method", values="rmse")[methods]
    w = 1 / e**2
    return w.div(w.sum(axis=1), axis=0)
