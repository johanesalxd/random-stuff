# Optimization Opportunities (30-Day Analysis)

## Slot Contention

- **Jobs with Contention:** 0
- **Impact:** No slot contention was detected. The workloads are extremely lightweight and execute instantly without competing for slot resources.
- **Recommendation:** No action required.

## Queue Pressure

- **Peak PENDING Jobs:** 9 pending jobs at `2026-06-03 02:36:00 UTC` (active jobs: 33, pending %: 27.3%)
- **Average Pending %:** Minimal (mostly 0% pending except for brief spikes under 10 seconds during multi-query scripts)
- **Queue Ceiling:** 1,000 queued interactive queries per project per region (hard limit)
- **Recommendation:** No project sharding or special queueing remediation is required since pending jobs are extremely rare and clear within seconds.

## Job Error Analysis

| Error Reason | Error Count | Error % | Capacity-Related |
|--------------|-------------|---------|------------------|
| invalidQuery | 2 | 66.7% | NO |
| stopped | 1 | 33.3% | NO |

**Capacity-Related Errors:**
- **rateLimitExceeded:** 0 occurrences (0%)
- **resourcesExceeded:** 0 occurrences (0%)
- **quotaExceeded:** 0 occurrences (0%)

## Job Impact Analysis

| Scenario | Commitment Slots | Total Jobs | Jobs Exceeding | % Jobs Exceeding | Slot-Hours Exceeding |
|----------|-----------------|------------|----------------|------------------|---------------------|
| P50 | 0.1 | 169 | 60 | 35.5% | 0.2 |
| Average | 2.6 | 169 | 24 | 14.2% | 0.2 |
| P90 | 4.7 | 169 | 13 | 7.7% | 0.1 |
| P95 | 7.0 | 169 | 6 | 3.6% | 0.1 |

**Interpretation:**
- This table demonstrates that even at a highly conservative virtual slot allocation level of 7.0 slots (P95), only 3.6% of jobs (6 jobs total) would ever exceed this capacity limit.
- Reserving even the minimum supported capacity of 50 slots under Standard or Enterprise reservations would comfortably absorb 100% of all workloads.

## Expensive Queries

| User | Query Count | TiB Scanned | Avg GB/Query |
|------|------------|-------------|--------------|
| admin@example.com | 150 | 0.0003 | 0.0027 |
| user@example.com | 14 | 0.0000 | 0.0000 |

**Recommendations:**
- All query scans are microscopic (less than 1 MB per query on average). No partitioning, clustering, or optimization of table scans is necessary.

## Slow Queries

| Job ID | User | Duration (s) | GB Processed | Slot-Hours |
|--------|------|--------------|--------------|------------|
| bquxjob_794d081b_19e44003c72 | admin@example.com | 169 | 0.0000 | 0.0488 |
| bquxjob_6f584b_19e440a13f5 | admin@example.com | 7 | 0.0000 | 0.0058 |
| bquxjob_42bebcc0_19e71e9b298 | admin@example.com | 4 | 0.0000 | 0.0050 |
| XUOffqQ9GCpOEPYKc73n5TOtOXK | admin@example.com | 4 | 0.0000 | 0.0050 |

**Interpretation:**
- The slowest query took 169 seconds but processed 0 bytes and consumed only 0.0488 slot-hours. This indicates it was likely an idle metadata command, a system-waiting task, or a small script loop rather than a heavy scanning query.

## Reservation Simulation

| Reservation Size | Hours Within | Hours Exceeding | Avg Utilization % |
|-----------------|--------------|-----------------|-------------------|
| 50 | 105 | 0 | 0.0058% |
| 100 | 105 | 0 | 0.0029% |
| 500 | 105 | 0 | 0.0006% |

**Optimal Size:** Standard on-demand (PAYG) pricing.
**Reservation alternative:** A Standard Edition reservation with a max autoscale limit of 50 slots would have an average utilization of **0.0058%**, making any reservation extremely wasteful due to the 1-minute minimum billing charge per autoscale block and 50-slot scale-up steps.

## Slot Recommender Cross-Check

- **Official Recommendation Available:** No
- **Recommended Slots / Edition:** N/A (No active recommendations found in `INFORMATION_SCHEMA.RECOMMENDATIONS_BY_PROJECT` for slots or cost savings)
- **Reconciliation:** The absence of recommendations is consistent with our heuristic findings. The query volume and slot usage are so small that the Slot Recommender has no basis or need to trigger rightsizing recommendations.
