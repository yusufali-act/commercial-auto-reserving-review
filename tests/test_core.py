"""Validate the hand-written methods against the `chainladder` package and
published figures for the Taylor & Ashe (1983) triangle used by Mack (1993).

`chainladder`'s "genins" sample is the Taylor-Ashe triangle.
"""

import chainladder as cl
import numpy as np
import pandas as pd
import pytest

from reserving.factors import average_factors, cdfs, fit_tail, flag_outliers
from reserving.methods import benktander, bornhuetter_ferguson, cape_cod, chain_ladder
from reserving.triangle import Triangle
from reserving.uncertainty import mack, odp_bootstrap


@pytest.fixture(scope="module")
def genins():
    g = cl.load_sample("genins")
    df = g.to_frame()
    df.index = df.index.year
    df.columns = [int(c) // 12 for c in df.columns]
    return Triangle(df.astype(float), "genins"), g


def test_triangle_basics(genins):
    tri, _ = genins
    assert tri.shape == (10, 10)
    assert tri.latest_diagonal().iloc[0] == pytest.approx(3901463)
    assert tri.latest_diagonal().iloc[-1] == pytest.approx(344014)
    inc = tri.incremental()
    np.testing.assert_allclose(inc.cumsum(axis=1).where(tri.values.notna()), tri.values)


def test_as_at_cuts_diagonals(genins):
    tri, _ = genins
    cut = tri.as_at(2007)
    assert list(cut.origins) == list(range(2001, 2008))
    assert cut.latest_age().loc[2007] == 1
    assert cut.latest_age().loc[2001] == 7
    assert cut.latest_diagonal().loc[2001] == pytest.approx(tri.values.loc[2001, 7])


def test_volume_factors_match_chainladder(genins):
    tri, g = genins
    ours = average_factors(tri, "volume").values
    theirs = cl.Development().fit(g).ldf_.values.flatten()
    np.testing.assert_allclose(ours, theirs, rtol=1e-10)


def test_simple_and_window_factors_match_chainladder(genins):
    tri, g = genins
    ours = average_factors(tri, "simple", n_periods=5).values
    theirs = cl.Development(average="simple", n_periods=5).fit(g).ldf_.values.flatten()
    np.testing.assert_allclose(ours, theirs, rtol=1e-10)


def test_exclusion_changes_only_that_column(genins):
    tri, _ = genins
    base = average_factors(tri)
    excl = average_factors(tri, exclude={(2004, 3)})
    assert excl.loc[3] != base.loc[3]
    pd.testing.assert_series_equal(base.drop(3), excl.drop(3), check_names=False)


def test_chain_ladder_matches_published_reserve(genins):
    tri, _ = genins
    res = chain_ladder(tri, cdfs(average_factors(tri)))
    reserve = (res["ultimate"] - res["latest"]).sum()
    # Mack (1993), Table 1: total reserve 18,680,856
    assert reserve == pytest.approx(18_680_856, rel=1e-6)


def test_bf_matches_chainladder(genins):
    tri, g = genins
    prior = pd.Series(8_000_000.0, index=tri.origins)
    ours = bornhuetter_ferguson(tri, cdfs(average_factors(tri)), prior)["ultimate"].values
    theirs = cl.BornhuetterFerguson(apriori=1).fit(g, sample_weight=g.latest_diagonal * 0 + 8_000_000).ultimate_
    np.testing.assert_allclose(ours, theirs.values.flatten(), rtol=1e-8)


def test_cape_cod_matches_chainladder(genins):
    tri, g = genins
    prem = pd.Series(10_000_000.0, index=tri.origins)
    ours = cape_cod(tri, cdfs(average_factors(tri)), prem)["ultimate"].values
    exposure = g.latest_diagonal * 0 + 10_000_000
    theirs = cl.CapeCod().fit(g, sample_weight=exposure).ultimate_.values.flatten()
    np.testing.assert_allclose(ours, theirs, rtol=1e-8)


def test_benktander_between_bf_and_cl(genins):
    tri, _ = genins
    c = cdfs(average_factors(tri))
    prior = pd.Series(8_000_000.0, index=tri.origins)
    u_cl = chain_ladder(tri, c)["ultimate"]
    u_bf = bornhuetter_ferguson(tri, c, prior)["ultimate"]
    u_bk = benktander(tri, c, prior)["ultimate"]
    lo, hi = np.minimum(u_cl, u_bf), np.maximum(u_cl, u_bf)
    assert ((u_bk >= lo - 1e-6) & (u_bk <= hi + 1e-6)).all()


def test_mack_matches_published(genins):
    tri, g = genins
    res = mack(tri)
    # Mack (1993) published total s.e. 2,447,095
    assert res.total_se == pytest.approx(2_447_095, rel=1e-4)
    # Mack (1993) Table: s.e. for origin 2 = 75,535 and origin 10 = 1,363,155
    assert res.table["mack_se"].iloc[1] == pytest.approx(75_535, abs=1)
    assert res.table["mack_se"].iloc[-1] == pytest.approx(1_363_155, abs=1)
    dev = cl.Development(sigma_interpolation="mack").fit(g)
    theirs = cl.MackChainladder().fit(dev.transform(g))
    np.testing.assert_allclose(
        res.table["mack_se"].values[1:], theirs.mack_std_err_.values[..., -1].flatten()[1:], rtol=1e-6
    )


def test_bootstrap_mean_and_se_close_to_mack(genins):
    tri, _ = genins
    b = odp_bootstrap(tri, n_sims=5000, seed=1)
    m = mack(tri)
    assert b.total.mean() == pytest.approx(m.total_reserve, rel=0.03)
    # ODP and Mack are different models; s.e. should be the same order (Taylor-Ashe ~13-16%)
    assert 0.10 < b.total.std() / b.total.mean() < 0.20


def test_tail_fit_recovers_known_curve():
    ages = np.arange(1, 10)
    ldf = pd.Series(1 + 0.8 * ages ** (-1.7), index=ages)
    t = fit_tail(ldf, "inverse_power")
    assert t.b == pytest.approx(1.7, rel=1e-6)
    assert t.tail_factor > 1


def test_outlier_flag(genins):
    tri, _ = genins
    v = tri.values.copy()
    v.loc[2003, 3:] *= 1.8  # inject a jump at age 2->3 for 2003
    flags = flag_outliers(Triangle(v))
    assert flags.loc[2003, 2]
