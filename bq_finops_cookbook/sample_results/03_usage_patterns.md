# Usage Patterns (30-Day Analysis)

> **Synthetic sample:** illustrative fixture only; not current project data or pricing.

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
