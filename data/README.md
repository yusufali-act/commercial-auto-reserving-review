# Data

## CAS Loss Reserving Database: commercial auto (`raw/comauto_pos.csv`)

* **Source:** Casualty Actuarial Society, *Loss Reserving Data Pulled From NAIC Schedule P* (Glenn Meyers & Peng Shi, 2011):
  <https://www.casact.org/publications-research/research/research-resources/loss-reserving-data-pulled-naic-schedule-p>
* **Download:** `make data` fetches the file from casact.org into `data/raw/`. It isn't committed here; the CAS distributes it.
* **Content:** Schedule P Part 1 data for 158 US insurer groups, commercial auto liability, accident years 1988-1997, development years 1-10 (the full square). USD thousands, net of reinsurance.

| Column | Meaning |
|---|---|
| `GRCODE`, `GRNAME` | NAIC company group code and name |
| `AccidentYear`, `DevelopmentYear`, `DevelopmentLag` | origin year, calendar year, age (1-10) |
| `IncurLoss_C` | incurred losses and allocated expenses **including bulk/IBNR** |
| `CumPaidLoss_C` | cumulative paid losses and allocated expenses |
| `BulkLoss_C` | bulk and IBNR reserves held by the company |
| `EarnedPremDIR_C`, `EarnedPremCeded_C`, `EarnedPremNet_C` | earned premium: direct, ceded, net |
| `Single` | 1 = single entity, 0 = group |
| `PostedReserve97_C` | reserves posted in the 1997 annual statement |

Derived: **case incurred = IncurLoss − BulkLoss** (claims-handler information only).

## SPLICE synthetic claims (`processed/splice_*.parquet`)

* **Generator:** `data/generate_splice.R` using the CRAN package [`SPLICE`](https://cran.r-project.org/package=SPLICE) (Avanzi, Taylor & Wang), built on `SynthETIC` (Avanzi, Taylor, Wang & Wong).
* **Scenario:** complexity 4 (inflation shock), 150 expected claims per quarter for 40 quarters, seed 20261116. Quarter 1 is labelled 2015 Q1; valuation 31/12/2024.
* `splice_claims.parquet`: one row per claim (occurrence, notification delay, settlement delay, uninflated size, number of payments).
* `splice_transactions.parquet`: one row per payment or case-estimate revision, **including transactions after the valuation date** (used only as hindsight).
* Committed so that Python users don't need R. Regenerate with `make splice`.
