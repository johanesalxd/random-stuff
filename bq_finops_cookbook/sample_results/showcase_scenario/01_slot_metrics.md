# Slot Usage Metrics

> **Synthetic sample:** illustrative fixture only; not current project data or pricing.

- **Analysis Window:** [2025-12-18T00:00:00Z, 2026-01-17T00:00:00Z)

Unless labelled otherwise, fixture query rows are OBSERVED, calculations are
DERIVED, interpretations are HEURISTIC, and proposed actions are RECOMMENDATION.

## All-Hour Percentile Distribution
- **p10:** 150 slots
- **p25:** 280 slots
- **p50:** 450 slots (median)
- **p75:** 850 slots
- **p95:** 1,800 slots
- **p99:** 2,300 slots
- **max:** 2,400 slots
- **Zero-Usage Hours:** 0%

## Active-Hour Distribution
- **Active Hours:** 720
- **p50:** 450 slots
- **p95:** 1,800 slots
- **p99:** 2,300 slots
- **max:** 2,400 slots
- **Average:** 520 slots

## Statistical Summary
- **Average:** 520 slots
- **Standard Deviation:** 410 slots

## Workload Characterization

### Stability Metric
- **Coefficient of Variation:** 0.79
- **Classification:** Moderate Variability
- **Interpretation:** The workload fluctuates significantly, likely due to daily batch jobs or user traffic peaks.

### Burstiness Metric
- **Burst Ratio (p95/p50):** 4.0
- **Classification:** High Burst
- **Interpretation:** The workload has significant spikes (4x median). A static baseline would either be wasteful (too high) or cause contention (too low).

## Query Status

| Query | Status | Evidence / Fallback | Scope or Blocking Note |
|---|---|---|---|
| 1.1 | PASS | Synthetic primary result | 720 all hours at 520 average reconcile to 374,400 slot-hours |

## Documentation Checks

| Claim | Source URL | Retrieved | Scope | PASS/GAP | Note |
|---|---|---|---|---|---|
| JOBS_TIMELINE slot usage | https://docs.cloud.google.com/bigquery/docs/information-schema-jobs-timeline | 2026-07-15 | Declared synthetic analysis window | PASS | Slot usage is not billed scaled capacity |
