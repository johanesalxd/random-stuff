# Project-Scoped Workload Consumption

> **Synthetic sample:** illustrative fixture only; not current project data or pricing.

- **Analysis Window:** [2025-12-18T00:00:00Z, 2026-01-17T00:00:00Z)

Unless labelled otherwise, fixture query rows are OBSERVED, calculations are
DERIVED, interpretations are HEURISTIC, and proposed actions are RECOMMENDATION.

## Workload Project

| Project ID | Slot-Hours | Job Count |
|------------|------------|-----------|
| ecommerce-prod | 374,400 | 1,200,000 |

## Analysis

- **Scope:** `OBSERVED` values represent the one explicitly qualified synthetic workload project.
- **Cross-project concentration:** `NOT AVAILABLE` from Query 1.2.
- **Recommendation:** Optimize this project locally. This single-project
  cookbook does not produce cross-project assignments or Hybrid recommendations;
  independently parallelized project runs remain separate evidence sets.

## Query Status

| Query | Status | Evidence / Fallback | Scope or Blocking Note |
|---|---|---|---|
| 1.2 | PASS | Synthetic primary result | One workload project; not a ranking |

## Documentation Checks

| Claim | Source URL | Retrieved | Scope | PASS/GAP | Note |
|---|---|---|---|---|---|
| Project-wide timeline visibility and overlap | https://docs.cloud.google.com/bigquery/docs/information-schema-jobs-timeline | 2026-07-16 | Synthetic workload project | PASS | Project scope is explicit and the derived creation bound retains observable overlapping timeslices |
