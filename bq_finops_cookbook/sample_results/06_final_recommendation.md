# Final Recommendation

> **Synthetic sample:** illustrative fixture only; not current project data or pricing.

- **Analysis Window:** [2026-05-05T00:00:00Z, 2026-06-04T00:00:00Z)

Unless labelled otherwise, fixture query rows are OBSERVED, calculations are
DERIVED, interpretations are HEURISTIC, and proposed actions are RECOMMENDATION.

## Current State Summary

- `OBSERVED`: one unused Standard reservation was present, with no assignments.
- `OBSERVED`: workload volume and bytes processed were negligible.
- `DERIVED`: all-hour p50 was 0.0001 slots and p95 was 0.0002 slots, giving a 2.00 burst ratio; rare p99 spikes do not change the negligible absolute usage.
- `HEURISTIC`: variability alone does not justify a reservation when absolute use is negligible.

## Evidence Quality

- **Confidence:** MEDIUM
- **Decision status:** PASS (remain on-demand; no purchase or migration proposed)
- **Query status:** 20 PASS, 0 BLOCKED, 5 NOT APPLICABLE; synthetic fixture with no live bq/gcloud execution
- **Timeline overlap preflight:** NOT RUN; the synthetic fixture assumes all observable overlapping timeslices are represented
- **Timeline history coverage:** SYNTHETIC ASSUMPTION; a live run must confirm retention and no in-window organization migration
- **IAM / visibility gaps:** recommender and billing export unavailable
- **Pricing verification:** NOT VERIFIED; no dollar savings claimed
- **Economic comparison:** REVIEW_REQUIRED; billed-byte fixture exists but regional pricing and capacity billing evidence do not
- **Reservation evidence scope:** one synthetic workload project

| Query | Status | Evidence / Fallback | Scope or Blocking Note |
|---|---|---|---|
| 0.1 | PASS | Primary fixture | Unused Standard reservation |
| 0.2 | PASS | Primary fixture | No assignments |
| 0.2a | PASS | Primary fixture | No commitments |
| 0.3 | NOT APPLICABLE | Not run | No reservation-backed compute |
| 0.4 | NOT APPLICABLE | Not run | No applicable baseline |
| 0.5 | PASS | Primary fixture | Positive-slot classification |
| 1.1 | PASS | Primary fixture | All/active-hour distributions |
| 1.2 | PASS | Primary fixture | One project only |
| 1.3 | PASS | Primary fixture | Pseudonymized local patterns |
| 4.1 | PASS | Primary fixture | No contention rows |
| 4.2 | PASS | Primary fixture | Billed bytes; pricing missing |
| 4.3 | PASS | Primary fixture | Hashed slow jobs |
| 4.4 | PASS | Primary fixture | Sensitivity only |
| 4.5 | PASS | Primary fixture | Weekly totals reconcile |
| 4.8 | PASS | Primary fixture | Hashed diagnostics plus failed compute |
| 4.9 | PASS | Primary fixture | Successful non-cached positive-compute distribution |
| 4.10 | PASS | Primary fixture | Brief queue rows |
| 4.11 | PASS | Primary fixture | Generic recommendation view returned zero rows; Slot Recommender was not applicable |
| 4.12 | PASS | Primary fixture | Observed zero insights |
| 4.13 | NOT APPLICABLE | Not run | BI Engine outside scope |
| 4.14 | NOT APPLICABLE | Not run | Dataset IDs absent |
| 5.1 | PASS | Primary fixture | Tiny Write API activity |
| 6.1 | PASS | Primary fixture | Storage types separate |
| 6.2 | PASS | Primary fixture | Triage only |
| 6.3 | NOT APPLICABLE | Not run | Comparison not requested |

## Recommended Strategy

**Choice:** On-demand

`HEURISTIC`: Absolute slot use and billed-byte volume are too small to justify reservation complexity. Reassess only after sustained growth or an SLO problem; spend remains unverified.

## Alternative Analysis

### Why Other Options Were Not Recommended

- **Standard autoscaling:** rejected because burstiness alone is insufficient when absolute use is tiny.
- **Enterprise baseline:** rejected because no stable baseline or commitment case exists.
- **Hybrid:** INELIGIBLE because only one workload project is in evidence.

## Optimization Actions

1. Add project-level query-cost controls and budgets.
2. Re-run the analysis after 30 complete days of material workload.
3. Obtain Slot Estimator/Recommender evidence before any capacity purchase.

## Recommended Actions (User-Executed)

No reservation changes are recommended. No GCP resource was changed.

## Validation Criteria

- [ ] Monthly query volume remains below the agreed budget threshold.
- [ ] p95 runtime meets the workload SLO.
- [ ] No sustained queue pressure appears.

## Documentation Checks

| Claim | Source URL | Retrieved | Scope | PASS/GAP | Note |
|---|---|---|---|---|---|
| Numeric BigQuery pricing | https://cloud.google.com/bigquery/pricing | 2026-07-15 | Synthetic location unspecified | GAP | No dollar estimate is permitted |
| JOBS_TIMELINE overlap and history coverage | https://docs.cloud.google.com/bigquery/docs/information-schema-jobs-timeline | 2026-07-16 | Synthetic workload window | PASS | Fixture assumes the derived overlap bound, retained history, and no in-window organization migration; no live probe ran |

## bq / gcloud Execution Notes

This is a synthetic offline fixture. No `bq` or `gcloud` command ran and no
active gcloud principal was used.

## Next Steps

1. Keep the workload on-demand.
2. Enable cost controls appropriate to the organization.
3. Reassess when usage or SLOs materially change.
