"""Data integrity, no-hindsight guarantees, and end-to-end checks."""

import numpy as np
import pandas as pd
import pytest

from reserving import backtest as B
from reserving import config as cfg
from reserving import data as D
from reserving.factors import average_factors, cdfs
from reserving.large_loss import inflation_index, project_nominal, to_real_terms
from reserving.methods import chain_ladder
from reserving.selection import BANDS, band_of, band_weights, blend


@pytest.fixture(scope="module")
def cas():
    return D.load_cas()


@pytest.fixture(scope="module")
def study(cas):
    return D.company(cas, cfg.STUDY_GRCODE)


# --------------------------------------------------------------------- CAS data
def test_full_square_and_upper_triangle(study):
    assert study.paid_full.shape == (10, 10)
    assert study.paid_full.values.notna().all().all()
    up = study.paid.values
    assert up.notna().sum().sum() == 55  # 10 + 9 + ... + 1
    assert study.paid.latest_age().loc[1997] == 1


def test_case_incurred_excludes_bulk(cas):
    d = cas.iloc[:500]
    np.testing.assert_allclose(d["case_incurred"], d["reported"] - d["bulk"])


def test_screen_uses_no_hindsight(cas):
    """Changing the lower triangle must not change the company screen."""
    tampered = cas.copy()
    future = ~tampered["observed"]
    tampered.loc[future, ["paid", "reported", "case_incurred"]] *= 3
    a = D.screen_companies(cas).set_index("grcode")
    b = D.screen_companies(tampered).set_index("grcode")
    pd.testing.assert_frame_equal(a, b)


def test_industry_excludes_study_company(cas):
    universe = D.backtest_universe(cas)
    ind = D.industry(cas, exclude=cfg.STUDY_GRCODE, grcodes=universe)
    ind_all = D.industry(cas, grcodes=universe)
    co = D.company(cas, cfg.STUDY_GRCODE)
    np.testing.assert_allclose(ind_all.premium - ind.premium, co.premium)


def test_actual_outcome_definition(study):
    expected = study.reported_full.values[10] - study.paid.latest_diagonal()
    pd.testing.assert_series_equal(study.actual_unpaid, expected, check_names=False)


# -------------------------------------------------------------------- back-test
def test_backtest_methods_and_no_lower_triangle_leak(cas):
    co = D.company(cas, cfg.STUDY_GRCODE)
    ind = D.industry(cas, exclude=cfg.STUDY_GRCODE, grcodes=D.backtest_universe(cas))
    prior = B.industry_prior_lr(ind.case, ind.premium)
    ult = B.standard_methods(co.paid, co.case, co.premium, prior)
    assert list(ult.columns) == B.METHODS
    # estimates must be identical whether we pass the full square cut to 1997 or the upper triangle
    ult2 = B.standard_methods(co.paid_full.as_at(1997), co.case_full.as_at(1997), co.premium, prior)
    pd.testing.assert_frame_equal(ult, ult2)


# -------------------------------------------------------------------- selection
def test_band_weights_sum_to_one(cas):
    bt = B.cross_company_backtest(cas, D.backtest_universe(cas)[:8])
    w = band_weights(bt, ["CL paid", "CL case", "Cape Cod paid", "Gen. Cape Cod case"])
    np.testing.assert_allclose(w.sum(axis=1), 1.0)
    assert list(w.index) == list(BANDS)
    assert band_of(1) == "1-2 (immature)" and band_of(10) == "6-10 (mature)"


def test_blend_is_weighted_average():
    ult = pd.DataFrame({"a": [100.0, 200.0], "b": [300.0, 400.0]}, index=[1996, 1997])
    w = pd.DataFrame({"a": [0.25, 0.5, 1.0], "b": [0.75, 0.5, 0.0]}, index=list(BANDS))
    out = blend(ult, pd.Series({1996: 2, 1997: 1}), w)
    assert out.loc[1997] == pytest.approx(0.25 * 200 + 0.75 * 400)


# -------------------------------------------------------------------- inflation
def test_zero_inflation_is_identity(study):
    idx = inflation_index({y: 0.0 for y in range(1988, 1998)}, base_year=1997)
    real = to_real_terms(study.paid, idx)
    np.testing.assert_allclose(real.values.fillna(0), study.paid.values.fillna(0))
    # and the inflation-adjusted projection with 0% future inflation equals the chain ladder
    f = average_factors(study.paid)
    ia = project_nominal(real, f, 1997, 0.0)["unpaid"]
    cl = chain_ladder(study.paid, cdfs(f))
    np.testing.assert_allclose(ia.values, (cl["ultimate"] - cl["latest"]).values)


def test_index_normalised_to_base():
    idx = inflation_index({2020: 0.0, 2021: 0.1, 2022: 0.1}, base_year=2022)
    assert idx.loc[2022] == pytest.approx(1.0)
    assert idx.loc[2020] == pytest.approx(1 / 1.21)


# ---------------------------------------------------------------------- SPLICE
def test_splice_triangles_reconcile():
    claims, txns = D.load_splice()
    snap = D.splice_snapshots(claims, txns, max_dev=25)
    full = D.splice_triangles(snap, max_dev=25)
    true = D.splice_true_ultimate(claims, txns)
    np.testing.assert_allclose(full["paid"].values[25].values, true.values, rtol=1e-9)
    paid_at_val = txns[txns["txn_time"] <= D.SPLICE_VALUATION_T].groupby("claim_no")["cumpaid"].max().sum()
    tri = D.splice_triangles(snap, max_dev=10)
    assert tri["paid"].upper().latest_diagonal().sum() == pytest.approx(paid_at_val)


# -------------------------------------------------------------------- pipeline
def test_pipeline_end_to_end():
    from reserving.pipeline import headline, run

    r = run(n_sims=300)
    h = headline(r)
    assert 65_000 < h["selected_unpaid"] < 76_000
    np.testing.assert_allclose(r.weights_selected.sum(axis=1), 1.0)
    # selected sits between the case and paid chain ladders in total
    assert h["method_unpaid"]["CL case"] < h["selected_unpaid"] < h["method_unpaid"]["CL paid"]
    # paid weight was reduced, never increased, for immature years
    assert (r.weights_selected.loc["1-2 (immature)", "CL paid"] <= r.weights_evidence.loc["1-2 (immature)", "CL paid"])
