# Usage Patterns

> **Synthetic sample:** illustrative fixture only; not current project data or pricing.

- **Analysis Window:** [2025-12-18T00:00:00Z, 2026-01-17T00:00:00Z)

Unless labelled otherwise, fixture query rows are OBSERVED, calculations are
DERIVED, interpretations are HEURISTIC, and proposed actions are RECOMMENDATION.

## Peak Usage Hours
- **Primary Peak:** Daily, 09:00 - 11:00 UTC (Morning Reporting) - 2,200 slots
- **Secondary Peak:** Daily, 01:00 UTC (ETL Batch) - 1,500 slots

## Off-Peak Hours
- **Lowest Usage:** 04:00 - 08:00 UTC
- **Recommended Batch Window:** Shift heavy ETL jobs to the 04:00-08:00 window to reduce contention.

## Weekly Trends
- **Trend:** +5% week-over-week growth.
- **Pattern:** Weekdays are 3x busier than weekends.

## Scheduling Recommendations
- **Action:** The "Morning Reporting" spike is causing the p95 to jump. Pre-calculate these reports during the off-peak window (04:00) using dbt or scheduled queries.

## Query Status

| Query | Status | Evidence / Fallback | Scope or Blocking Note |
|---|---|---|---|
| 1.3 | PASS | Synthetic primary result | Project-local patterns only |
| 4.5 | PASS | Synthetic primary result | Weekly trend evidence present |

## Documentation Checks

| Claim | Source URL | Retrieved | Scope | PASS/GAP | Note |
|---|---|---|---|---|---|
| JOBS_TIMELINE regional scope | https://docs.cloud.google.com/bigquery/docs/information-schema-jobs-timeline | 2026-07-15 | Synthetic workload location | PASS | Location remains explicit |
