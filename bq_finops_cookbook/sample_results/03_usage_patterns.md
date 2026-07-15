# Usage Patterns

> **Synthetic sample:** illustrative fixture only; not current project data or pricing.

- **Analysis Window:** [2026-05-05T00:00:00Z, 2026-06-04T00:00:00Z)

Unless labelled otherwise, fixture query rows are OBSERVED, calculations are
DERIVED, interpretations are HEURISTIC, and proposed actions are RECOMMENDATION.

## Peak Usage Hours

- **Primary Peak:** Monday, Hour 14 (UTC) - 0.1413 slots (principal fingerprint `9d5e…`)
- **Secondary Peak:** Wednesday, Hour 2 (UTC) - 0.0118 slots (principal fingerprint `9d5e…`)
- **Tertiary Peak:** Thursday, Hour 4 (UTC) - 0.0064 slots (principal fingerprint `9d5e…`)

## Off-Peak Hours

- **Lowest Usage:** Weekends and non-working hours have near-zero active query usage. Synthetic background workloads include:
  - principal `svc-a91e…` executes tiny administrative queries (~0.0006 - 0.0008 slot-hours) at Hour 11 and Hour 19 UTC daily.
  - principal `svc-40c2…` executes daily load jobs around Hour 12 to 15 UTC, consuming ~0.001 slot-hours.
- **Recommended Batch Window:** Since there is zero slot contention or substantial workload, batch jobs can be scheduled at any time of day. However, Hour 16:00 to 22:00 UTC has the cleanest absolute quiet window.

## Weekly Trends

| Week | Total Slot-Hours | Days in Week | Trend |
|------|-----------------|--------------|-------|
| 18 | 0.001 | 1 | - |
| 19 | 0.015 | 7 | Up |
| 20 | 0.077 | 7 | Up |
| 21 | 0.020 | 7 | Down |
| 22 | 0.036 | 7 | Up |
| 23 | 0.156 | 2 | Up (Highest usage) |

## Scheduling Recommendations

- **Non-critical workloads:** Can run anytime, but preferably during Hour 16:00 to 22:00 UTC when ad-hoc user query activity is absent.
- **Peak Capacity Planning:** Peak hourly slot usage remains well below 1 slot, meaning no capacity reservation or planning is required.

## Query Status

| Query | Status | Evidence / Fallback | Scope or Blocking Note |
|---|---|---|---|
| 1.3 | PASS | Synthetic primary result | Pseudonymized project-local patterns |
| 4.5 | PASS | Synthetic primary result | Weekly rows sum to 0.305 slot-hours |

## Documentation Checks

| Claim | Source URL | Retrieved | Scope | PASS/GAP | Note |
|---|---|---|---|---|---|
| JOBS_TIMELINE scope and retention | https://docs.cloud.google.com/bigquery/docs/information-schema-jobs-timeline | 2026-07-15 | Synthetic workload location | PASS | Region and project remain explicit |
