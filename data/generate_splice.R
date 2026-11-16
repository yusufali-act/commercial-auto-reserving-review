# Generate a synthetic claim-level dataset with SPLICE (Avanzi, Taylor & Wang).
#
# Why synthetic? Real claim-level reserving data with full transaction histories
# is essentially never public. SPLICE is a peer-reviewed simulator that produces
# individual claims with occurrence/notification/settlement dates, partial
# payments AND case-estimate (incurred) revisions - i.e. the kind of extract a
# reserving team receives from a claims system. Crucially it also gives us the
# *future* transactions, so every method can be scored against the true outcome.
#
# Scenario: complexity 4 ("inflation shock"):
#   * notification and settlement delays depend on claim size (large claims
#     are reported and settled later - so they dominate the tail)
#   * base inflation ~2% p.a. throughout
#   * from quarter 30 (mid-2022 on our calendar labelling) payments are subject
#     to an additional 10% p.a. superimposed inflation - mirroring the claims
#     inflation spike UK/US motor insurers experienced from 2022
#
# Quarter 1 is labelled 2015 Q1, so the 10 accident years read 2015-2024 and
# the valuation date (end of quarter 40) is 31/12/2024.
#
# Run once:  Rscript data/generate_splice.R
# Output:    data/processed/splice_claims.parquet
#            data/processed/splice_transactions.parquet

suppressMessages({
  library(SPLICE)
  library(arrow)
})

SEED <- 20261116
N_PERIODS <- 40          # quarters -> 10 accident years
CLAIMS_PER_PERIOD <- 150 # expected claims per quarter (~600 a year)

set_parameters(ref_claim = 200000, time_unit = 1 / 4)

out <- generate_data(
  n_claims_per_period = CLAIMS_PER_PERIOD,
  n_periods = N_PERIODS,
  complexity = 4,
  data_type = c("claims", "incurred"),
  random_seed = SEED,
  verbose = TRUE
)

claims <- out$claim_dataset
txns <- out$incurred_dataset

dir.create("data/processed", showWarnings = FALSE, recursive = TRUE)
write_parquet(claims, "data/processed/splice_claims.parquet")
write_parquet(txns, "data/processed/splice_transactions.parquet")

cat("claims:", nrow(claims), " transactions:", nrow(txns), "\n")
