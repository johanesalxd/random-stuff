# Project-Scoped Workload Consumption

> **Synthetic sample:** illustrative fixture only; not current project data or pricing.

- **Analysis Window:** [2026-05-05T00:00:00Z, 2026-06-04T00:00:00Z)

Unless labelled otherwise, fixture query rows are OBSERVED, calculations are
DERIVED, interpretations are HEURISTIC, and proposed actions are RECOMMENDATION.

## Workload Project

| Project ID | Slot-Hours | Job Count |
|------------|------------|-----------|
| sample-finops-project-123456 | 0.305 | 160 |

## Analysis

- **Scope:** This project-scoped fixture does not rank multiple projects.
- **Recommendation:** Absolute use is negligible; no reservation assignment complexity is justified.

## Query Status

| Query | Status | Evidence / Fallback | Scope or Blocking Note |
|---|---|---|---|
| 1.2 | PASS | Synthetic primary result | One workload project; not a ranking |

## Documentation Checks

| Claim | Source URL | Retrieved | Scope | PASS/GAP | Note |
|---|---|---|---|---|---|
| Project-wide timeline visibility and overlap | https://docs.cloud.google.com/bigquery/docs/information-schema-jobs-timeline | 2026-07-16 | Synthetic workload project | PASS | Requires project-wide visibility; derived creation bound retains observable overlapping timeslices |
