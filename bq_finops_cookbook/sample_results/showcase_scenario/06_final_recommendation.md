# Final Recommendation

> **Synthetic sample:** illustrative fixture only; not current project data or pricing.

- **Analysis Window:** [2025-12-18T00:00:00Z, 2026-01-17T00:00:00Z)

Unless labelled otherwise, fixture query rows are OBSERVED, calculations are
DERIVED, interpretations are HEURISTIC, and proposed actions are RECOMMENDATION.

## Current State Summary

- `OBSERVED`: p50=450, p95=1,800, max=2,400 synthetic slots.
- `DERIVED`: the workload exceeds the current 1,600-slot Standard-edition ceiling.
- `HEURISTIC`: steady baseline use plus large peaks merits Enterprise capacity evaluation.
- `OFFICIAL`: the verified Standard reservation maximum used by this dated fixture is 1,600 slots.

## Evidence Quality

- **Confidence:** MEDIUM
- **Decision status:** REVIEW_REQUIRED
- **Query status:** 18 PASS, 3 BLOCKED, 4 NOT APPLICABLE; synthetic fixture with no live bq/gcloud execution
- **IAM / visibility gaps:** current Slot Recommender output unavailable
- **Pricing verification:** NOT VERIFIED; no dollar savings claimed
- **Economic comparison:** REVIEW_REQUIRED; current pricing and actual capacity billing evidence are unavailable
- **Reservation evidence scope:** one synthetic workload project; Hybrid is ineligible

| Query | Status | Evidence / Fallback | Scope or Blocking Note |
|---|---|---|---|
| 0.1 | PASS | Primary fixture | No reservations |
| 0.2 | PASS | Primary fixture | No assignments |
| 0.2a | PASS | Primary fixture | No current commitments or retained change rows |
| 0.3 | NOT APPLICABLE | Not run | No reservation-backed compute |
| 0.4 | NOT APPLICABLE | Not run | No baseline |
| 0.5 | PASS | Primary fixture | Positive-slot classification |
| 1.1 | PASS | Primary fixture | 720 all/active hours |
| 1.2 | PASS | Primary fixture | One project only |
| 1.3 | PASS | Primary fixture | Project-local patterns |
| 4.1 | PASS | Primary fixture | Contention evidence |
| 4.2 | PASS | Primary fixture | Billed bytes; economics incomplete |
| 4.3 | PASS | Primary fixture | Hashed slow jobs |
| 4.4 | PASS | Primary fixture | Sensitivity only |
| 4.5 | PASS | Primary fixture | Weekly trend |
| 4.8 | PASS | Primary fixture | Hashed diagnostics |
| 4.9 | PASS | Primary fixture | Per-job distribution |
| 4.10 | BLOCKED | Per-second rows absent | Contention is not queue evidence |
| 4.11 | PASS | Primary fixture | Generic recommendation view returned zero rows; Slot Recommender remains separately BLOCKED |
| 4.12 | PASS | Primary fixture | Contention insight present |
| 4.13 | NOT APPLICABLE | Not run | BI Engine outside scope |
| 4.14 | BLOCKED | Dataset evidence absent | Hashed table is triage only |
| 5.1 | NOT APPLICABLE | Not run | Ingestion outside scope |
| 6.1 | PASS | Primary fixture | Storage types separate |
| 6.2 | PASS | Primary fixture | Triage only |
| 6.3 | BLOCKED | Prices/threshold absent | No dollar sensitivity |

## Recommended Strategy

**Choice:** REVIEW_REQUIRED — Enterprise evaluation with baseline plus autoscaling

`HEURISTIC`: Start scenario testing around a 500-slot baseline plus 1,900 additional autoscaling slots, for a 2,400-slot total maximum. Final sizing requires Slot Estimator/Recommender evidence, current pricing, queue/runtime SLOs, and administrator review.

## Alternative Analysis

### Why Other Options Were Not Recommended

- **On-demand:** viable fallback while evidence is incomplete.
- **Standard autoscaling:** rejected because the synthetic peak exceeds the documented 1,600-slot maximum.
- **Enterprise baseline:** candidate, subject to economics and SLOs.
- **Hybrid:** INELIGIBLE because only one workload project is in evidence.

## Optimization Actions

1. Optimize the highest-slot queries before purchasing capacity.
2. Move noncritical batch work away from peak windows.
3. Compare on-demand and Enterprise scenarios using verified prices and actual capacity billing evidence.

## Recommended Actions (User-Executed)

The analyst does not change any cloud resource. The following is a recommendation for the user to perform.

### Recommendation 1: Evaluate an Enterprise reservation with baseline + autoscaling
- **Intended outcome:** ~500-slot baseline plus autoscaling up to a 2,400-slot maximum, covering steady demand while absorbing peaks that exceed the 1,600-slot Standard ceiling.
- **Prechecks:** reconcile size with Slot Estimator/Recommender, confirm reservation location and administration project, verify current edition/location pricing.
- **Rollback / lock-in:** slot-hour billing is flexible; any capacity commitment carries a fixed term — verify before purchase.
- **How to apply:** [Manage workload reservations](https://docs.cloud.google.com/bigquery/docs/reservations-tasks).

No assignment or commitment is recommended until project ownership and pricing are verified.

## Validation Criteria

- [ ] Slot Estimator/Recommender evidence reconciled.
- [ ] Queue and p95 runtime SLOs improve or remain healthy.
- [ ] Current edition/location prices support the economics.
- [ ] Rollback and assignment ownership are approved.

## Documentation Checks

| Claim | Source URL | Retrieved | Scope | PASS/GAP | Note |
|---|---|---|---|---|---|
| Standard maximum reservation size | https://docs.cloud.google.com/bigquery/docs/editions-intro | 2026-07-15 | Standard edition | PASS | Dated synthetic fixture; refresh before live use |
| Reservation flags and increments | https://docs.cloud.google.com/bigquery/docs/reservations-tasks | 2026-07-15 | User-executed Enterprise recommendation | PASS | Recheck preview and location support before implementation |
| Numeric pricing | https://cloud.google.com/bigquery/pricing | 2026-07-15 | Synthetic location unspecified | GAP | No dollar savings claimed |

## bq / gcloud Execution Notes

This is a synthetic offline fixture. No `bq` or `gcloud` command ran and no
active gcloud principal was used.

## Next Steps

1. Run the read-only analysis against an approved project.
2. Collect current Slot Estimator/Recommender and pricing evidence.
3. Have a BigQuery administrator review any final recommendation.
