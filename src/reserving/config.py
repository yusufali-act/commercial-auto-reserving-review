"""Selected assumptions for the study company, in one place.

Each choice is justified in the notebook named alongside it. Keeping them here
means every notebook, the pipeline and the report use identical assumptions,
and a reviewer can see every judgement at a glance.
"""

STUDY_GRCODE = 2712                 # Pennsylvania National Ins Grp - notebook 01
VALUATION_YEAR = 1997               # reserves as at 31/12/1997

# --- Development factors (notebook 03) ------------------------------------
FACTOR_METHOD = "volume"            # volume-weighted: weights years by size, standard & least noisy
FACTOR_PERIODS = None               # all years; 5yr/3yr shown as sensitivities
FACTOR_EXCLUSIONS: set[tuple[int, int]] = set()   # none - flagged ratios are recent years (possible trend, not noise)

# --- Tail factors beyond age 10 (notebook 03) ------------------------------
# Evidence: curve fits give 1.001-1.005 (paid) / 1.000-1.003 (case); the
# industry's own reported/paid at age 10 is 1.004 and reported/case 1.001.
TAIL_PAID = 1.005
TAIL_CASE = 1.002

# --- Prior for BF / Cape Cod (notebook 04) ---------------------------------
# Generalised Cape Cod on case incurred: the company's own loss ratios with
# decay 0.75 so that each year leans on its neighbours. Chosen over an
# industry prior because the company's loss ratio has drifted away from the
# industry's since 1993 (an industry prior would understate recent years).
CAPE_COD_DECAY = 0.75

# --- Method weights by maturity (notebook 08) ------------------------------
# Starting point: inverse-MSE weights from the cross-company back-test,
# estimated on the other 30 companies (notebook 06). Judgement overlay:
# paid weight halved for ages 1-5 because the paid/case ratio has drifted
# upward since 1993 and the cause (faster settlement vs weaker case
# reserves) cannot be resolved without claim counts.
SELECTION_METHODS = ["CL paid", "CL case", "Cape Cod paid", "Gen. Cape Cod case"]
PAID_WEIGHT_HAIRCUT = {"1-2 (immature)": 0.5, "3-5 (developing)": 0.5, "6-10 (mature)": 1.0}

# --- Uncertainty ------------------------------------------------------------
N_BOOTSTRAP = 10_000
SEED = 1997

# --- SPLICE claim-level module (notebook 07) --------------------------------
SPLICE_VALUATION = 2024
SPLICE_EXPOSURE = 10_000.0          # vehicle-years per accident year (constant by construction)
LARGE_LOSS_THRESHOLD = 1_000_000    # in valuation-year money, indexed back by accident year
FUTURE_INFLATION = 0.122            # = observed 2023-24 claims inflation, assumed to persist
