# Reserve Review: Commercial Auto Liability

**Company:** Pennsylvania National Insurance Group (NAIC group 2712)
**Valuation date:** 31 December 1997
**Basis:** net of reinsurance, undiscounted, losses including allocated loss adjustment expenses; USD thousands unless stated
**Data:** NAIC Schedule P Part 1 via the CAS Loss Reserving Database; supplementary claim-level analysis on SPLICE synthetic data

*An illustrative portfolio exercise on public data. The company is real, but this isn't an opinion on its actual reserves.*

---

## 1. Executive summary

| | USD 000 |
|---|---:|
| **Selected best-estimate unpaid claims** | **70,522** |
| of which case reserves | 37,289 |
| of which IBNR | 33,233 |
| Interquartile range | 66,279 - 74,478 |
| 95th / 99.5th percentile | 80,995 / 87,784 |
| Company's posted reserve (for comparison) | 75,716 |

* Methods give between **$61m and $90m**. The spread is driven almost entirely by **paid vs case incurred** data, not by factor or tail choices.
* Paid-to-case ratios rose from accident year 1993, indicating either faster settlement (paid methods overstate) or weaker case reserving (case methods understate). Without claim counts this can't be resolved, so the selection blends both bases, with weights set by **back-test evidence across 30 other insurers** and a reduced paid weight for immature years.
* The BF/Cape Cod prior is based on the company's own loss-ratio experience with a trend (generalised Cape Cod), because the company has run well above the industry since 1994.
* Stochastic models (Mack, ODP bootstrap) give a CV of ~9%, but the paid and case models barely overlap. **Model risk exceeds statistical risk**, and the range above should be read as a lower bound.
* **Hindsight:** the actual outcome was **$68.7m**. The selection was **+2.7%**, the paid chain ladder +31.1%, the company's posted reserve +10.2%.

**Recommendation:** obtain claim counts (reported / closed / open) to run Berquist-Sherman diagnostics on the paid/case shift. This is the single largest source of uncertainty.

## 2. Scope and data

**Line:** commercial auto liability, accident years 1988-1997. Net earned premium $463m in total, ~$46m a year.

**Data used at the valuation date:** cumulative paid and incurred losses by accident year and development year (upper triangle), bulk/IBNR held, net earned premium. **Case incurred** is defined as Schedule P incurred minus bulk/IBNR, so it reflects claims-handler information only.

**Hindsight:** Schedule P continues each accident year to ten development years. The data after 1997 was not used for any assumption and appears only in section 9.

**Company selection:** 158 companies were screened on information available at 31/12/1997 only (premium ≥ $20m every year, premium CV ≤ 30%, no zero/negative cells, ≤ 5 negative paid movements). Nine passed. Penn National was chosen for its representative size, stable volume, clean data and material IBNR. Automated tests confirm the screen is unaffected by post-1997 data.

**Data checks:** full 10×10 square present; no missing values; premium constant within accident year; no negative paid increments; 5 negative case movements (normal). Industry benchmark = aggregate of 30 other clean companies, excluding Penn National.

## 3. Diagnostics

| Test | Result | Implication |
|---|---|---|
| Paid / case incurred by age | 1993+ ratios higher (age 1: 0.44 vs 0.38; age 2: 0.66 vs 0.58); diagonals 3-6% above the 1988-92 level since 1994 | settlement speed or case strength changed; paid and case CL will disagree |
| Case link ratios | 1993 and 1994 at age 2-3 flagged as high (1.23, 1.19 vs median 1.10) | consistent with weaker case reserves, or the start of a trend |
| ODP residuals by calendar year | alternating sign, no run | no explicit inflation adjustment needed |
| CL loss ratio vs industry | 1988-92: 67% vs 68%; 1994-97: 82-86% vs ~65% | company has drifted above the market, so an industry prior would understate |

## 4. Assumptions

| Assumption | Selected | Alternatives considered | Rationale |
|---|---|---|---|
| Averaging basis | volume-weighted, all years, both bases | simple, medial; latest 5 / 3 years | least noisy; consistent with Mack/bootstrap; alternatives shown as sensitivities (paid +$3-5m, case up to +$11m on short windows) |
| Exclusions | none | exclude 1993/94 case age 2-3 (−$1.9m) | flagged ratios are the most recent; may be a new trend, not noise |
| Paid tail | 1.005 | curve fits 1.001-1.005; industry 1.004 | inverse-power fit, just above industry evidence |
| Case tail | 1.002 | curve fits 1.000-1.003; industry 1.001 | midpoint of fits |
| Prior loss ratio | generalised Cape Cod, decay 0.75: 70% (1988) rising to 79% (1997) | industry × relativity (~64-69%); plain Cape Cod (74%) | company's own data, allows the observed upward trend, stable against thin recent data |

## 5. Results by method (total unpaid)

| Method | Paid basis | Case incurred basis |
|---|---:|---:|
| Chain ladder | 90,088 | 69,235 |
| Bornhuetter-Ferguson (industry prior) | 61,504 | 61,699 |
| Cape Cod | 72,310 | 65,462 |
| Generalised Cape Cod (0.75) | n/a | 67,042 |
| Benktander (Gen. Cape Cod prior) | n/a | 68,546 |

All methods agree within ~$1m for 1988-92. The differences sit in 1994-97, where paid CL implies loss ratios up to 102%.

## 6. Selection

**Approach.** For each maturity band, the four candidate methods (CL and Cape Cod, on paid and case) are weighted by inverse mean squared error measured on **30 other companies' actual outcomes** (in an out-of-sample test, this blend beat every single method and nearly removed the bias). The paid weight is then **halved for ages 1-5**, the one adjustment for a company-specific risk the industry evidence can't see.

| Band | CL paid | CL case | Cape Cod paid | Gen. Cape Cod case |
|---|---:|---:|---:|---:|
| Ages 1-2 | 6% | 36% | 12% | 45% |
| Ages 3-5 | 10% | 39% | 11% | 40% |
| Ages 6-10 | 36% | 14% | 34% | 17% |

**Selected reserve by accident year**

| AY | Age | Premium | Paid | Case incurred | Selected ultimate | Selected LR | Selected unpaid | of which IBNR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1988 | 10 | 42,874 | 27,449 | 27,568 | 27,606 | 64.4% | 157 | 38 |
| 1989 | 9 | 38,829 | 29,444 | 29,619 | 29,623 | 76.3% | 179 | 4 |
| 1990 | 8 | 43,001 | 30,656 | 30,743 | 30,935 | 71.9% | 279 | 192 |
| 1991 | 7 | 41,840 | 23,465 | 24,176 | 24,185 | 57.8% | 720 | 9 |
| 1992 | 6 | 44,525 | 27,168 | 27,612 | 28,541 | 64.1% | 1,373 | 929 |
| 1993 | 5 | 50,923 | 33,803 | 35,987 | 36,662 | 72.0% | 2,859 | 675 |
| 1994 | 4 | 56,601 | 39,702 | 44,210 | 46,544 | 82.2% | 6,842 | 2,334 |
| 1995 | 3 | 54,609 | 32,406 | 40,550 | 45,353 | 83.1% | 12,947 | 4,803 |
| 1996 | 2 | 47,204 | 21,831 | 32,432 | 40,566 | 85.9% | 18,735 | 8,134 |
| 1997 | 1 | 42,412 | 9,076 | 19,392 | 35,507 | 83.7% | 26,431 | 16,115 |
| **Total** | | **462,818** | **275,000** | **312,289** | **345,522** | **74.7%** | **70,522** | **33,233** |

**Rationale.**
*1988-92:* ≥ 95% paid; paid methods most accurate at these ages in the back-test; all methods agree.
*1993-95:* case incurred is 90-99% reported, against 66-91% paid, so ~80% weight on case methods.
*1996-97:* paid CDFs of 2.1 and 4.8 make paid CL highly leveraged; ~45% weight on Gen. Cape Cod, the best single method at these ages in the back-test.

**Reasonableness.** Selected 1994-97 loss ratios (82-86%) follow the company's upward trend without the 102% implied by paid CL for 1997. The implied share paid is above the historical pattern for recent years, consistent with faster settlement. IBNR is 1.6× case reserves for 1997.

## 7. Uncertainty

| Model | Mean / CL | s.e. | CV | 99.5th pct |
|---|---:|---:|---:|---:|
| Mack, paid | 88,272 | 7,615 | 8.6% | n/a |
| Mack, case incurred (unpaid basis) | 68,548 | 5,997 | 8.7% | n/a |
| ODP bootstrap, paid (10,000 sims) | 88,471 | 7,523 | 8.5% | 109,180 |
| ODP bootstrap, case incurred | 68,495 | 7,732 | 11.3% | 91,108 |

Only 0.2% of paid simulations fall below the case bootstrap's median. Each model measures process and parameter risk *given itself*; neither captures the risk of being the wrong model. The selected range uses the case-basis Mack CV with a lognormal shape, and is presented alongside the method spread.

## 8. Sensitivities

| Alternative | Total unpaid | vs selected |
|---|---:|---:|
| No paid-weight adjustment (pure evidence weights) | 72,545 | +2.9% |
| 5-year factors instead of all-year | 72,847 | +3.3% |
| Industry prior instead of generalised Cape Cod | 68,179 | −3.3% |
| Tails +1% on both bases | 72,182 | +2.4% |
| Case-based methods only | 68,037 | −3.5% |

Reasonable alternative judgements move the result by ±2-4%, inside the interquartile range.

## 9. Hindsight review

| | Total unpaid | Error |
|---|---:|---:|
| Paid chain ladder | 90,088 | +31.1% |
| Case chain ladder | 69,235 | +0.8% |
| Gen. Cape Cod (case) | 67,042 | −2.4% |
| BF with industry prior | 61,699 | −10.2% |
| **Selected** | **70,522** | **+2.7%** |
| Company posted | 75,716 | +10.2% |
| **Actual** (reported incurred at age 10 − paid at 1997) | **68,691** | |

* The paid/case shift was mainly **faster settlement**. Paid CL over-reserved at every valuation from 1994 to 1997 (+17% to +42%).
* 1996 developed better than any method projected (selected $18.7m vs actual $15.4m), offset by 1994-95 being slightly light. A good total can hide offsetting year-level errors, which is why reserves need monitoring through actual-vs-expected analysis.
* At a 1994 valuation, with only seven development years, case methods were ~22% short because the fitted tail was too light. Tail judgement matters most on short triangles.

## 10. Claim-level supplement (SPLICE)

On 5,905 synthetic claims (53,724 transactions) with a mid-2022 inflation shock (2% → 12% a year):

| Method | vs true outstanding |
|---|---:|
| Naive paid CL | −31% |
| Naive incurred CL | −9% |
| Inflation-adjusted paid CL (12% future) | −12% |
| Inflation-adjusted Cape Cod (12% future) | −7% |
| Capped incurred CL + large-loss load | −11% |

Claim counts showed stable closure rates and case reserves tracking inflation, which ruled out the settlement/case-strength explanations that couldn't be tested on Schedule P. Deflating past payments without a realistic **future** inflation assumption made the result slightly worse. Capping large losses roughly halved link-ratio volatility from age 4, but didn't fix the level, because the binding issue was inflation.

## 11. Limitations and reliances

* Schedule P data is relied on as filed; no reconciliation to ledgers was possible.
* No claim counts, gross data, reinsurance detail or expense (ULAE) reserves.
* Undiscounted, no explicit risk margin; an IFRS 17 or Solvency II basis would need discounting, a risk adjustment / risk margin and a one-year reserve-risk view.
* Back-test evidence comes from other companies' later outcomes, standing in for the actual-vs-expected history and industry studies an actuary would hold.
* "Actual" outcome is reported incurred at age 10, which still includes a small amount of IBNR.

## 12. Next steps

1. Request claim counts and run Berquist-Sherman settlement-rate and case-adequacy adjustments.
2. Set up quarterly actual-vs-expected monitoring by accident year against the selected pattern.
3. Extend to gross/net and reinsurance recoveries; add discounting and a risk margin for an IFRS 17 view.
4. Add Merz-Wüthrich one-year reserve risk for a Solvency II SCR view.
