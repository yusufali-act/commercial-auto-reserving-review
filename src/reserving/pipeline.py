"""End-to-end reserve review for the study company.

`run()` reproduces every headline number in the README and report from the
raw CAS file, using the assumptions in `config.py`. Notebooks call the same
functions so that the narrative and the numbers cannot drift apart.

    python -m reserving.pipeline        # writes outputs/tables/*.csv and outputs/results.json
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import stats

from . import backtest as B
from . import config as cfg
from . import data as D
from .factors import average_factors, cdfs
from .methods import benktander, bornhuetter_ferguson, cape_cod, cape_cod_elr, chain_ladder, expected_loss_ratio
from .selection import BANDS, band_of, band_weights, blend
from .uncertainty import mack, odp_bootstrap

TABLES = D.ROOT / "outputs" / "tables"


@dataclass
class Review:
    co: D.CompanyData
    ind: D.CompanyData
    cdf_paid: pd.Series
    cdf_case: pd.Series
    prior_lr: pd.Series                 # industry LR x company relativity (for BF "industry prior")
    results: dict[str, pd.DataFrame]
    ultimates: pd.DataFrame
    unpaid: pd.DataFrame
    weights_evidence: pd.DataFrame
    weights_selected: pd.DataFrame
    selected: pd.DataFrame
    backtest: pd.DataFrame
    extras: dict = field(default_factory=dict)


def company_prior(co: D.CompanyData, ind: D.CompanyData, cdf_case: pd.Series) -> pd.Series:
    """Industry loss ratio by year x company's relativity on its mature years (1988-1992)."""
    ind_lr = B.industry_prior_lr(ind.case, ind.premium, cfg.TAIL_CASE)
    co_lr = chain_ladder(co.case, cdf_case)["ultimate"] / co.premium
    mature = co.case.latest_age() >= 6
    rel = (co_lr[mature] * co.premium[mature]).sum() / (ind_lr[mature] * co.premium[mature]).sum()
    return ind_lr * rel


def run_methods(co, cdf_paid, cdf_case, prior_lr) -> dict[str, pd.DataFrame]:
    prem = co.premium
    prior = prem * prior_lr
    gcc_elr = cape_cod_elr(co.case, cdf_case, prem, decay=cfg.CAPE_COD_DECAY)
    return {
        "CL paid": chain_ladder(co.paid, cdf_paid),
        "CL case": chain_ladder(co.case, cdf_case),
        "BF paid": bornhuetter_ferguson(co.paid, cdf_paid, prior),
        "BF case": bornhuetter_ferguson(co.case, cdf_case, prior),
        "Cape Cod paid": cape_cod(co.paid, cdf_paid, prem),
        "Cape Cod case": cape_cod(co.case, cdf_case, prem),
        "Gen. Cape Cod case": cape_cod(co.case, cdf_case, prem, decay=cfg.CAPE_COD_DECAY),
        "Benktander case": benktander(co.case, cdf_case, prem * gcc_elr),
        "ELR": expected_loss_ratio(prem, prior_lr),
    }


def selection_weights(bt: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Evidence weights (other companies only) and the judgement-adjusted weights."""
    evidence_methods = ["CL paid", "CL case", "Cape Cod paid", "Gen. Cape Cod case"]
    w_ev = band_weights(bt[bt["grcode"] != cfg.STUDY_GRCODE], evidence_methods)
    w = w_ev.copy()
    for band, cut in cfg.PAID_WEIGHT_HAIRCUT.items():
        paid_cols = [c for c in w.columns if "paid" in c]
        case_cols = [c for c in w.columns if "paid" not in c]
        freed = w.loc[band, paid_cols].sum() * (1 - cut)
        w.loc[band, paid_cols] *= cut
        w.loc[band, case_cols] += freed * w.loc[band, case_cols] / w.loc[band, case_cols].sum()
    return w_ev, w


def run(n_sims: int = cfg.N_BOOTSTRAP, write: bool = False) -> Review:
    df = D.load_cas()
    universe = D.backtest_universe(df)
    co = D.company(df, cfg.STUDY_GRCODE)
    ind = D.industry(df, exclude=cfg.STUDY_GRCODE, grcodes=universe)

    f_paid = average_factors(co.paid, cfg.FACTOR_METHOD, cfg.FACTOR_PERIODS, cfg.FACTOR_EXCLUSIONS)
    f_case = average_factors(co.case, cfg.FACTOR_METHOD, cfg.FACTOR_PERIODS, cfg.FACTOR_EXCLUSIONS)
    cdf_paid, cdf_case = cdfs(f_paid, cfg.TAIL_PAID), cdfs(f_case, cfg.TAIL_CASE)
    prior_lr = company_prior(co, ind, cdf_case)

    results = run_methods(co, cdf_paid, cdf_case, prior_lr)
    ult = pd.DataFrame({k: v["ultimate"] for k, v in results.items()})
    paid_latest = co.paid.latest_diagonal()
    unpaid = ult.sub(paid_latest, axis=0)

    bt = B.cross_company_backtest(df, universe)
    w_ev, w_sel = selection_weights(bt)
    ages = co.paid.latest_age()
    sel_ult = blend(ult, ages, w_sel)

    # Uncertainty: Mack CV on the case-incurred CL applied to the selected unpaid,
    # lognormal shape (positively skewed, non-negative).
    m_case, m_paid = mack(co.case), mack(co.paid)
    boot = odp_bootstrap(co.paid, n_sims=n_sims, seed=cfg.SEED)
    cl_case_unpaid = unpaid["CL case"].sum()
    cv = m_case.total_se / cl_case_unpaid
    sel_total = float((sel_ult - paid_latest).sum())
    s2 = np.log(1 + cv**2)
    mu = np.log(sel_total) - s2 / 2
    pct = {q: float(np.exp(mu + np.sqrt(s2) * stats.norm.ppf(q))) for q in (0.25, 0.5, 0.75, 0.95, 0.995)}

    selected = pd.DataFrame(
        {
            "age": ages.astype(int),
            "band": ages.map(lambda a: band_of(int(a))),
            "premium": co.premium,
            "paid": paid_latest,
            "case_incurred": co.case.latest_diagonal(),
            "selected_ultimate": sel_ult,
            "selected_unpaid": sel_ult - paid_latest,
            "selected_ibnr": sel_ult - co.case.latest_diagonal(),
            "selected_lr": sel_ult / co.premium,
            "actual_unpaid_hindsight": co.actual_unpaid,
        }
    )

    extras = {
        "mack_case": m_case,
        "mack_paid": m_paid,
        "bootstrap_paid": boot,
        "selected_cv": cv,
        "selected_percentiles": pct,
        "posted_reserve_97": co.posted_reserve_97,
        "universe": universe,
    }
    review = Review(co, ind, cdf_paid, cdf_case, prior_lr, results, ult, unpaid, w_ev, w_sel, selected, bt, extras)
    if write:
        write_outputs(review)
    return review


def headline(r: Review) -> dict:
    u = r.unpaid.sum()
    sel = r.selected
    e = r.extras
    boot = e["bootstrap_paid"]
    return {
        "company": r.co.name,
        "valuation": f"31/12/{cfg.VALUATION_YEAR}",
        "units": "USD 000, net of reinsurance",
        "selected_unpaid": round(float(sel["selected_unpaid"].sum())),
        "selected_ibnr": round(float(sel["selected_ibnr"].sum())),
        "selected_range_p25_p75": [round(e["selected_percentiles"][0.25]), round(e["selected_percentiles"][0.75])],
        "selected_p95": round(e["selected_percentiles"][0.95]),
        "selected_p99_5": round(e["selected_percentiles"][0.995]),
        "selected_cv": round(e["selected_cv"], 3),
        # ELR ignores the data entirely, so its total (incl. mature years) is not meaningful
        "method_unpaid": {k: round(float(v)) for k, v in u.items() if k != "ELR"},
        "posted_reserve_97": round(e["posted_reserve_97"]),
        "actual_unpaid_hindsight": round(float(sel["actual_unpaid_hindsight"].sum())),
        "mack_paid_se": round(e["mack_paid"].total_se),
        "mack_case_se": round(e["mack_case"].total_se),
        "bootstrap_paid_mean": round(float(boot.total.mean())),
        "bootstrap_paid_p99_5": round(float(np.quantile(boot.total, 0.995))),
        "bootstrap_paid_p0_5": round(float(np.quantile(boot.total, 0.005))),
    }


def write_outputs(r: Review) -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    r.unpaid.round(0).to_csv(TABLES / "unpaid_by_method.csv")
    r.selected.round(3).to_csv(TABLES / "selected_reserve.csv")
    r.weights_selected.round(3).to_csv(TABLES / "selection_weights.csv")
    r.weights_evidence.round(3).to_csv(TABLES / "evidence_weights.csv")
    B.error_by_age(r.backtest).round(4).to_csv(TABLES / "backtest_error_by_age.csv", index=False)
    (D.ROOT / "outputs" / "results.json").write_text(json.dumps(headline(r), indent=2))


if __name__ == "__main__":
    rev = run(write=True)
    print(json.dumps(headline(rev), indent=2))
