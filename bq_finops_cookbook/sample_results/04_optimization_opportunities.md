# Optimization Opportunities

> **Synthetic sample:** illustrative fixture only; not current project data or pricing.

- **Analysis Window:** [2026-05-05T00:00:00Z, 2026-06-04T00:00:00Z)

Unless labelled otherwise, fixture query rows are OBSERVED, calculations are
DERIVED, interpretations are HEURISTIC, and proposed actions are RECOMMENDATION.

## Slot Contention

- **Jobs with Contention:** 0
- **Impact:** No engine-reported slot-contention insight appeared in this synthetic fixture.
- **Recommendation:** No capacity action from this signal alone.

## Queue Pressure

- **Peak Pending Interactive Jobs:** 9 at `2026-06-03 02:36:00 UTC`
- **Average Pending Interactive Jobs per Observed JOBS_TIMELINE Second:** negligible in the observed synthetic rows
- **Observed JOBS_TIMELINE Seconds:** synthetic fixture count not retained; no wall-clock average claimed
- **Queue Ceiling:** 1,000 queued interactive queries per project per region
- **Recommendation:** No project sharding is justified by this fixture.

## Job Error Analysis

| Error Reason | Error Count | Error % | Positive-Compute Failures | Failed Slot-Hours | Recent Hashed Handles | Diagnosis Status |
|--------------|-------------|---------|---------------------------|-------------------|-----------------------|------------------|
| invalidQuery | 2 | 66.7% | 2 | 0.03 | jobs `3a0c…`, `8b16…` | REQUIRES_DIAGNOSIS |
| stopped | 1 | 33.3% | 1 | 0.01 | job `19de…` | REQUIRES_DIAGNOSIS |

Error reasons are diagnostic categories, not proof of capacity pressure or one root cause.

## Per-job Average Slot Distribution

| Scenario | Avg Job Slot Threshold | Total Jobs | Jobs Above | % Jobs Above | Slot-Hours Above |
|----------|------------------------|------------|------------|--------------|------------------|
| P50 | 0.1 | 160 | 60 | 37.5% | 0.2 |
| Average | 2.6 | 157 | 24 | 15.3% | 0.2 |
| P90 | 4.7 | 157 | 13 | 8.3% | 0.1 |
| P95 | 7.0 | 157 | 6 | 3.8% | 0.1 |

**Interpretation:** This describes the 157 successful, non-cached,
positive-compute jobs with valid duration. The three failed positive-compute
jobs remain in the error evidence above. The distribution does not model
concurrency, reservation demand, queueing, autoscaling, or the number of jobs
affected by a reservation size.

## Expensive Queries

| Principal Fingerprint | Workload Fingerprint | Type | Query Count | TiB Processed | TiB Billed | Table Fingerprints |
|-----------------------|----------------------|------|-------------|---------------|------------|--------------------|
| `9d5e…` | `2a81…` | Google-provided normalized query hash | 146 | 0.0003 | 0.0003 | `a031…` |
| `04f8…` | `JOB:71b4…` | salted job fingerprint | 14 | 0.0000 | 0.0000 | `c29f…` |

Economic comparison remains `REVIEW_REQUIRED` because the regional price and capacity billing comparison are unavailable.

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

## Slot Recommender Cross-Check

- **Official Recommendation Available:** NOT APPLICABLE
- **Supported Scenario:** Capacity recommendation analysis was not triggered by this negligible fixture
- **Recommended Slots / Edition:** N/A
- **Estimated Savings:** N/A
- **API / IAM Status:** Not evaluated
- **Reconciliation:** `NOT APPLICABLE`; Query 4.11 remains the separate generic recommendation probe.

## General Cost Recommendations

- **`INFORMATION_SCHEMA.RECOMMENDATIONS_BY_PROJECT`:** no relevant synthetic rows
- **Slot Recommender / Slot Estimator:** `UNVERIFIED`
- **Reconciliation:** Absence from the general recommendations view is not evidence that Slot Recommender has no capacity recommendation. Obtain the dedicated recommender/estimator evidence before capacity sizing.

## Query Performance Insights

- **Status:** PASS
- **Findings:** No qualifying engine-generated performance insight appeared in this synthetic fixture.

## BI Engine Diagnostics

- **Status:** NOT APPLICABLE
- **Findings:** BI Engine diagnostics were outside this fixture's declared workload scope.

## Partition and Cluster Triage

- **Status:** NOT APPLICABLE
- **Findings:** No approved dataset IDs were supplied.

## Query Status

| Query | Status | Evidence / Fallback | Scope or Blocking Note |
|---|---|---|---|
| 4.1 | PASS | Synthetic primary result | Observed no engine contention insight |
| 4.2 | PASS | Synthetic primary result | Null-reservation billed-byte evidence; pricing unavailable |
| 4.3 | PASS | Synthetic primary result | Privacy-safe slow-job handles |
| 4.4 | PASS | Synthetic primary result | Historical sensitivity only |
| 4.8 | PASS | Synthetic primary result | Aggregate reasons, failed compute, and hashed handles |
| 4.9 | PASS | Synthetic primary result | Successful non-cached positive-compute distribution only |
| 4.10 | PASS | Synthetic primary result | Brief queue rows, far below limit |
| 4.11 | PASS | Synthetic primary result | Generic recommendation view returned zero applicable rows |
| 4.12 | PASS | Synthetic primary result | Zero qualifying insights observed |
| 4.13 | NOT APPLICABLE | Not run | BI Engine outside declared scope |
| 4.14 | NOT APPLICABLE | Not run | Dataset IDs not supplied |

## Documentation Checks

| Claim | Source URL | Retrieved | Scope | PASS/GAP | Note |
|---|---|---|---|---|---|
| Generic recommendations | https://docs.cloud.google.com/bigquery/docs/information-schema-recommendations | 2026-07-15 | Synthetic workload project | PASS | Empty generic rows do not prove no slot recommendation |
| Slot Recommender applicability | https://docs.cloud.google.com/bigquery/docs/slot-recommender | 2026-07-15 | Synthetic negligible workload | PASS | Capacity recommendation analysis was not applicable; generic rows remain separate |
| JOBS_TIMELINE overlap partitioning | https://docs.cloud.google.com/bigquery/docs/information-schema-jobs-timeline | 2026-07-16 | Synthetic sensitivity and queue evidence | PASS | Fixture assumes the derived creation bound includes all observable in-window timeslices |
