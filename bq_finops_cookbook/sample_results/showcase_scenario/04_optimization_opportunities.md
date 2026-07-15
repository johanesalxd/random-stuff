# Optimization Opportunities

> **Synthetic sample:** illustrative fixture only; not current project data or pricing.

- **Analysis Window:** [2025-12-18T00:00:00Z, 2026-01-17T00:00:00Z)

Unless labelled otherwise, fixture query rows are OBSERVED, calculations are
DERIVED, interpretations are HEURISTIC, and proposed actions are RECOMMENDATION.

## Slot Contention
- **Jobs with Contention:** 450 engine-reported slot-contention jobs
- **Impact:** Separate synthetic runtime evidence shows morning reports delayed by up to 15 minutes; contention is correlated evidence, not proof of a single cause.

## Job Error Analysis
| Error Reason | Count | % | Recent Hashed Handles | Diagnosis Status |
|--------------|-------|---|-----------------------|------------------|
| rateLimitExceeded | 12 | 70.6% | jobs `51af…`, `a034…` | REQUIRES_DIAGNOSIS |
| resourcesExceeded | 5 | 29.4% | job `fa82…` | REQUIRES_DIAGNOSIS |

## Queue Pressure

- **Status:** BLOCKED in this fixture
- **Finding:** Per-second queued-job evidence was not included; contention rows do not substitute for queue counts.

## Expensive Queries
*Top synthetic null-reservation workloads by bytes. Pricing was not verified, so no dollar estimate is shown.*

| Principal Fingerprint | Workload Fingerprint | Query Count | TiB Processed | TiB Billed | Table Fingerprints |
|-----------------------|----------------------|-------------|---------------|------------|--------------------|
| `7fa1…` | `0a42…` | 15,000 | 483.40 | 483.40 | `98cd…` |
| `0bc4…` | `9e17…` | 200 | 146.48 | 146.48 | `51af…` |

**Recommendations:**
- **Partitioning:** Workload fingerprint `9e17…` processes 750 GiB on average. Review the table represented by fingerprint `51af…` for date partitioning after an approved private lookup.
- **BI Dashboard:** The BI tool is scanning too much data. Switch to a summarized/aggregated table for the dashboard.

Economic comparison is `REVIEW_REQUIRED`: billed-byte evidence is present, but current regional prices and actual capacity billing evidence are absent.

## Job Impact Analysis
*If we committed to the **Average (520 slots)**:*
- **Jobs Above Threshold:** 35% had per-job average slots above 520; this does not model reservation concurrency or imply on-demand spillover.
- **Impact:** No performance conclusion is available from this threshold alone; validate with Slot Estimator/Recommender and runtime SLO testing.

## Per-job Average Slot Distribution

- **Status:** PASS
- **Finding:** 35% of synthetic jobs exceeded the 520-slot per-job average threshold; this is not concurrent reservation demand.

## Slow Queries

- **Status:** PASS
- **Finding:** Privacy-safe slow-job handles were reviewed; duration alone did not establish a root cause.

## Historical Demand Sensitivity

- **Status:** PASS
- **Finding:** The 520-slot threshold is a historical sensitivity point, not a reservation simulation.

## Slot Recommender Cross-Check

- **Status:** BLOCKED
- **Finding:** Current dedicated Slot Recommender/Estimator evidence was unavailable.

## General Cost Recommendations

- **Status:** PASS
- **Finding:** No applicable active generic cost-recommendation row appeared; this does not establish Slot Recommender absence.

## Query Performance Insights

- **Status:** PASS
- **Finding:** Engine-reported slot-contention rows were present.

## BI Engine Diagnostics

- **Status:** NOT APPLICABLE
- **Finding:** BI Engine was outside the declared synthetic scope.

## Partition and Cluster Triage

- **Status:** BLOCKED
- **Finding:** The private table mapping and approved dataset-scoped audit were not supplied; the hashed handle is triage only.

## Query Status

| Query | Status | Evidence / Fallback | Scope or Blocking Note |
|---|---|---|---|
| 4.1 | PASS | Synthetic primary result | Engine contention evidence |
| 4.2 | PASS | Synthetic primary result | Bytes only; economics require review |
| 4.3 | PASS | Synthetic primary result | Hashed slow-job handles |
| 4.4 | PASS | Synthetic primary result | Historical sensitivity only |
| 4.8 | PASS | Synthetic primary result | Reasons plus hashed handles |
| 4.9 | PASS | Synthetic primary result | Per-job distribution only |
| 4.10 | BLOCKED | No per-second queue evidence | Contention is not a fallback |
| 4.11 | PASS | Synthetic primary result | Generic recommendation view returned zero applicable rows; external Slot Recommender remains separately BLOCKED |
| 4.12 | PASS | Synthetic primary result | Contention insight present |
| 4.13 | NOT APPLICABLE | Not run | BI Engine outside declared scope |
| 4.14 | BLOCKED | Dataset-scoped evidence unavailable | No raw table mapping persisted |

## Documentation Checks

| Claim | Source URL | Retrieved | Scope | PASS/GAP | Note |
|---|---|---|---|---|---|
| Slot Recommender scenarios | https://docs.cloud.google.com/bigquery/docs/slot-recommender | 2026-07-15 | Synthetic Enterprise evaluation | GAP | Current dedicated recommendation was unavailable |
| Query performance insights | https://docs.cloud.google.com/bigquery/docs/query-insights | 2026-07-15 | Synthetic query jobs | PASS | Insights remain diagnostic evidence |
