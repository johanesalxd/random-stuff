# Optimization Opportunities (30-Day Analysis)

> **Synthetic sample:** illustrative fixture only; not current project data or pricing.

## Slot Contention

- **Jobs with Contention:** 0
- **Impact:** No engine-reported slot-contention insight appeared in this synthetic fixture.
- **Recommendation:** No capacity action from this signal alone.

## Queue Pressure

- **Peak Pending Interactive Jobs:** 9 at `2026-06-03 02:36:00 UTC`
- **Average Pending Interactive Jobs:** negligible outside brief synthetic spikes
- **Queue Ceiling:** 1,000 queued interactive queries per project per region
- **Recommendation:** No project sharding is justified by this fixture.

## Job Error Analysis

| Error Reason | Error Count | Error % | Diagnosis Status |
|--------------|-------------|---------|------------------|
| invalidQuery | 2 | 66.7% | REQUIRES_DIAGNOSIS |
| stopped | 1 | 33.3% | REQUIRES_DIAGNOSIS |

Error reasons are diagnostic categories, not proof of capacity pressure or one root cause.

## Per-job Average Slot Distribution

| Scenario | Avg Job Slot Threshold | Total Jobs | Jobs Above | % Jobs Above | Slot-Hours Above |
|----------|------------------------|------------|------------|--------------|------------------|
| P50 | 0.1 | 169 | 60 | 35.5% | 0.2 |
| Average | 2.6 | 169 | 24 | 14.2% | 0.2 |
| P90 | 4.7 | 169 | 13 | 7.7% | 0.1 |
| P95 | 7.0 | 169 | 6 | 3.6% | 0.1 |

**Interpretation:** This describes historical per-job averages only. It does not model concurrency, reservation demand, queueing, autoscaling, or the number of jobs affected by a reservation size.

## Expensive Queries

| Principal Fingerprint | Query Count | TiB Scanned | Avg GiB/Query |
|-----------------------|-------------|-------------|---------------|
| `9d5e…` | 150 | 0.0003 | 0.0027 |
| `04f8…` | 14 | 0.0000 | 0.0000 |

No scan-cost optimization is justified by the synthetic absolute volume.

## Slow Queries

| Job Fingerprint | Principal Fingerprint | Duration (s) | GiB Processed | Slot-Hours |
|-----------------|-----------------------|--------------|---------------|------------|
| `2c7d…` | `9d5e…` | 169 | 0.0000 | 0.0488 |
| `ae12…` | `9d5e…` | 7 | 0.0000 | 0.0058 |

Duration alone does not identify a capacity bottleneck; inspect the engine insights and job metadata.

## Historical Demand Sensitivity

| Candidate Threshold | Hours At/Below | Hours Above | Threshold Utilization % |
|--------------------|----------------|-------------|-------------------------|
| 50 | 720 | 0 | 0.0058% |
| 100 | 720 | 0 | 0.0029% |
| 500 | 720 | 0 | 0.0006% |

This is all-hour historical threshold sensitivity, not a reservation simulation or cost forecast. The absolute workload remains too small to justify reservation complexity.

## General Cost Recommendations

- **`INFORMATION_SCHEMA.RECOMMENDATIONS_BY_PROJECT`:** no relevant synthetic rows
- **Slot Recommender / Slot Estimator:** `UNVERIFIED`
- **Reconciliation:** Absence from the general recommendations view is not evidence that Slot Recommender has no capacity recommendation. Obtain the dedicated recommender/estimator evidence before capacity sizing.
