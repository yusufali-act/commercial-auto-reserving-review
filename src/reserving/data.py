"""Data loading.

Two sources:

1. CAS Loss Reserving Database (Meyers & Shi, 2011) - Schedule P, Part 1
   commercial auto data for US insurers, accident years 1988-1997, ten years
   of development each. Because each accident year is followed for ten years
   the file contains the *full square*: the lower triangle (development after
   31/12/1997) is the actual outcome, which is what makes honest back-testing
   possible.

2. SPLICE synthetic claim-level data (see data/generate_splice.R): individual
   claims with payment and case-estimate transactions. Used to build
   triangles from transactions and to study large losses and inflation.
"""

from __future__ import annotations

import urllib.request
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .triangle import Triangle

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"

CAS_URL = "https://www.casact.org/sites/default/files/2021-04/comauto_pos.csv"
CAS_FILE = RAW / "comauto_pos.csv"
VALUATION_YEAR = 1997

COLUMNS = {
    "GRCODE": "grcode",
    "GRNAME": "company",
    "AccidentYear": "ay",
    "DevelopmentYear": "cal",
    "DevelopmentLag": "dev",
    "IncurLoss_C": "reported",        # case incurred + bulk/IBNR held by the company
    "CumPaidLoss_C": "paid",
    "BulkLoss_C": "bulk",
    "EarnedPremDIR_C": "premium_direct",
    "EarnedPremCeded_C": "premium_ceded",
    "EarnedPremNet_C": "premium",
    "Single": "single_entity",
    "PostedReserve97_C": "posted_reserve_97",
}


# --------------------------------------------------------------------------- #
# CAS Schedule P
# --------------------------------------------------------------------------- #
def download_cas(dest: Path = CAS_FILE, url: str = CAS_URL) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        urllib.request.urlretrieve(url, dest)
    return dest


def load_cas(path: Path = CAS_FILE) -> pd.DataFrame:
    """Load and tidy the CAS commercial auto file (all companies, full square)."""
    if not Path(path).exists():
        download_cas(Path(path))
    df = pd.read_csv(path).rename(columns=COLUMNS)[list(COLUMNS.values())]
    df["company"] = df["company"].str.strip()
    # Losses are net of reinsurance, in USD thousands. Schedule P "incurred"
    # includes the company's bulk (IBNR) reserve; case incurred removes it so
    # that paid vs incurred compares claims-handler information only.
    df["case_incurred"] = df["reported"] - df["bulk"]
    df["observed"] = df["cal"] <= VALUATION_YEAR
    return df.sort_values(["grcode", "ay", "dev"]).reset_index(drop=True)


def screen_companies(df: pd.DataFrame) -> pd.DataFrame:
    """One row per company with the statistics used to pick a study company.

    Only the *upper* triangle (information available at 31/12/1997) is used,
    so the choice of company is not influenced by how its reserves turned out.
    """
    up = df[df["observed"]]
    rows = []
    for (g, name), d in up.groupby(["grcode", "company"]):
        prem = d.groupby("ay")["premium"].first()
        paid_inc = d.groupby("ay")["paid"].diff()
        case_inc = d.groupby("ay")["case_incurred"].diff()
        latest = d.sort_values("dev").groupby("ay").last()
        rows.append(
            {
                "grcode": g,
                "company": name,
                "premium_min": prem.min(),
                "premium_mean": prem.mean(),
                "premium_cv": prem.std() / prem.mean() if prem.mean() > 0 else np.nan,
                "ceded_share": d.groupby("ay")["premium_ceded"].first().sum() / max(d.groupby("ay")["premium_direct"].first().sum(), 1),
                "zero_or_negative_cells": int((d["paid"] <= 0).sum() + (d["case_incurred"] <= 0).sum()),
                "negative_paid_increments": int((paid_inc < 0).sum()),
                "negative_case_increments": int((case_inc < 0).sum()),
                "bulk_share_latest": latest["bulk"].sum() / max(latest["reported"].sum(), 1),
                "reported_lr_latest": latest["reported"].sum() / prem.sum() if prem.sum() > 0 else np.nan,
                "posted_reserve_97": d["posted_reserve_97"].iloc[0],
            }
        )
    s = pd.DataFrame(rows)
    s["eligible"] = (
        (s["premium_min"] >= 20_000)
        & (s["premium_cv"] <= 0.30)
        & (s["zero_or_negative_cells"] == 0)
        & (s["negative_paid_increments"] <= 5)
    )
    return s.sort_values("premium_mean", ascending=False).reset_index(drop=True)


def backtest_universe(df: pd.DataFrame, min_premium: float = 2_000) -> list[int]:
    """Companies clean enough to include in the cross-company back-test.

    Looser than the study-company screen (we want many companies) but excludes
    files where triangles are not meaningful: zero/negative cumulative values,
    tiny books, or premium that swings wildly.
    """
    s = screen_companies(df)
    ok = (
        (s["premium_min"] >= min_premium)
        & (s["premium_cv"] <= 0.5)
        & (s["zero_or_negative_cells"] == 0)
        & (s["negative_paid_increments"] <= 8)
    )
    return s.loc[ok, "grcode"].tolist()


@dataclass
class CompanyData:
    grcode: int
    name: str
    paid_full: Triangle        # full square (includes hindsight)
    case_full: Triangle
    reported_full: Triangle    # case + bulk, i.e. the company's own estimate
    premium: pd.Series
    posted_reserve_97: float

    @property
    def paid(self) -> Triangle:
        return self.paid_full.upper()

    @property
    def case(self) -> Triangle:
        return self.case_full.upper()

    @property
    def actual_ultimate(self) -> pd.Series:
        """Proxy for the true ultimate: company's reported incurred after 10 years.

        Uses reported incurred (case + bulk) at development age 10, which is
        the standard choice in the CAS loss reserve literature (e.g. Meyers
        2015). Paid at age 10 is also shown in the back-test as a lower bound.
        """
        return self.reported_full.values[10]

    @property
    def actual_unpaid(self) -> pd.Series:
        return self.actual_ultimate - self.paid.latest_diagonal()


def company(df: pd.DataFrame, grcode: int) -> CompanyData:
    d = df[df["grcode"] == grcode]
    if d.empty:
        raise KeyError(grcode)

    def tri(col):
        return Triangle.from_long(d, "ay", "dev", col, name=f"{col}")

    return CompanyData(
        grcode=grcode,
        name=d["company"].iloc[0],
        paid_full=tri("paid"),
        case_full=tri("case_incurred"),
        reported_full=tri("reported"),
        premium=d.groupby("ay")["premium"].first().astype(float),
        posted_reserve_97=float(d["posted_reserve_97"].iloc[0]),
    )


def industry(df: pd.DataFrame, exclude: int | None = None, grcodes: list[int] | None = None) -> CompanyData:
    """Aggregate of companies (optionally excluding the study company) as a benchmark."""
    d = df if grcodes is None else df[df["grcode"].isin(grcodes)]
    if exclude is not None:
        d = d[d["grcode"] != exclude]
    agg = d.groupby(["ay", "dev"], as_index=False)[["paid", "case_incurred", "reported", "premium", "posted_reserve_97"]].sum()
    agg["grcode"] = -1
    agg["company"] = "Industry"
    prem = d.groupby(["grcode", "ay"])["premium"].first().groupby("ay").sum()
    posted = d.groupby("grcode")["posted_reserve_97"].first().sum()

    def tri(col):
        return Triangle.from_long(agg, "ay", "dev", col, name=f"industry {col}")

    return CompanyData(-1, "Industry", tri("paid"), tri("case_incurred"), tri("reported"), prem.astype(float), float(posted))


# --------------------------------------------------------------------------- #
# SPLICE claim-level data
# --------------------------------------------------------------------------- #
SPLICE_FIRST_YEAR = 2015      # label quarter 1 as 2015 Q1 so the 10 accident years read 2015-2024
SPLICE_VALUATION_T = 40.0     # end of quarter 40 = 31/12/2024


def load_splice() -> tuple[pd.DataFrame, pd.DataFrame]:
    claims = pd.read_parquet(PROCESSED / "splice_claims.parquet")
    txns = pd.read_parquet(PROCESSED / "splice_transactions.parquet")
    claims["ay"] = SPLICE_FIRST_YEAR + ((claims["occurrence_period"] - 1) // 4).astype(int)
    claims["notification_time"] = claims["occurrence_time"] + claims["notidel"]
    claims["settlement_time"] = claims["notification_time"] + claims["setldel"]
    txns = txns.merge(claims[["claim_no", "ay", "occurrence_time"]], on="claim_no")
    txns["case_os"] = txns["OCL"]
    return claims, txns.sort_values(["claim_no", "txn_time"]).reset_index(drop=True)


def splice_snapshots(claims: pd.DataFrame, txns: pd.DataFrame, max_dev: int = 25) -> pd.DataFrame:
    """Each claim's cumulative paid and incurred at every calendar year end.

    Returns one row per claim x development year (from its accident year),
    including future years beyond the valuation date so that true outcomes
    are known.
    """
    grid = claims[["claim_no", "ay", "notification_time", "settlement_time", "claim_size"]].merge(
        pd.DataFrame({"dev": np.arange(1, max_dev + 1)}), how="cross"
    )
    grid["cal"] = grid["ay"] + grid["dev"] - 1
    grid["t"] = (grid["cal"] - SPLICE_FIRST_YEAR + 1) * 4.0
    grid = grid.sort_values("t")
    tx = txns[["claim_no", "txn_time", "incurred", "cumpaid"]].sort_values("txn_time")
    snap = pd.merge_asof(grid, tx, left_on="t", right_on="txn_time", by="claim_no", direction="backward")
    snap[["incurred", "cumpaid"]] = snap[["incurred", "cumpaid"]].fillna(0.0)
    snap["reported"] = snap["notification_time"] <= snap["t"]
    snap["closed"] = snap["settlement_time"] <= snap["t"]
    snap["case_os"] = snap["incurred"] - snap["cumpaid"]
    snap["observed"] = snap["t"] <= SPLICE_VALUATION_T
    return snap.sort_values(["claim_no", "dev"]).reset_index(drop=True)


def splice_triangles(snap: pd.DataFrame, max_dev: int = 10) -> dict[str, Triangle]:
    """Aggregate claim snapshots into full-square triangles (upper = observed)."""
    s = snap[snap["dev"] <= max_dev]
    agg = s.groupby(["ay", "dev"]).agg(
        paid=("cumpaid", "sum"),
        incurred=("incurred", "sum"),
        reported_count=("reported", "sum"),
        closed_count=("closed", "sum"),
    ).reset_index()
    return {c: Triangle.from_long(agg, "ay", "dev", c, name=c) for c in ["paid", "incurred", "reported_count", "closed_count"]}


def splice_true_ultimate(claims: pd.DataFrame, txns: pd.DataFrame) -> pd.Series:
    final = txns.groupby("claim_no")["cumpaid"].max()
    return claims.set_index("claim_no")["ay"].to_frame().join(final).groupby("ay")["cumpaid"].sum().rename("true_ultimate")
