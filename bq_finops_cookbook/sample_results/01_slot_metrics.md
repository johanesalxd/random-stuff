# Slot Usage Metrics

> **Synthetic sample:** illustrative fixture only; not current project data or pricing.

- **Analysis Window:** [2026-05-05T00:00:00Z, 2026-06-04T00:00:00Z)

Unless labelled otherwise, fixture query rows are OBSERVED, calculations are
DERIVED, interpretations are HEURISTIC, and proposed actions are RECOMMENDATION.

## All-Hour Percentile Distribution

- **p10:** 0 slots
- **p25:** 0.0001 slots
- **p50:** 0.0001 slots (median)
- **p75:** 0.0002 slots
- **p95:** 0.0002 slots
- **p99:** 0.0107 slots
- **max:** 0.1443 slots
- **Zero-Usage Hours:** 15.3%

## Active-Hour Distribution

- **Active Hours:** 610
- **p50:** 0.0002 slots
- **p95:** 0.0003 slots
- **p99:** 0.0107 slots
- **max:** 0.1443 slots
- **Average:** 0.0005 slots

## Statistical Summary

- **Average:** 0.0004236 slots
- **Standard Deviation:** 0.0054695 slots

## Workload Characterization

### Stability Metric

- **Coefficient of Variation:** 12.91
- **Classification:** Highly variable
- **Interpretation:** The workload exhibits extremely high relative variability because it consists of brief, sporadic user queries and scheduled loads separated by long periods of near-total idle time.

### Burstiness Metric

- **Burst Ratio (p95/p50):** 2.00
- **Classification:** Medium burst
- **Interpretation:** The workload has a moderate p95-to-median ratio of 2.00, while a few rare spikes drive p99 and the maximum. Absolute slot use remains extremely low.

## Query Status

| Query | Status | Evidence / Fallback | Scope or Blocking Note |
|---|---|---|---|
| 1.1 | PASS | Synthetic primary result | 720 all hours and 610 active hours reconcile to 0.305 slot-hours |

## Documentation Checks

| Claim | Source URL | Retrieved | Scope | PASS/GAP | Note |
|---|---|---|---|---|---|
| JOBS_TIMELINE slot-ms and overlap semantics | https://docs.cloud.google.com/bigquery/docs/information-schema-jobs-timeline | 2026-07-16 | Declared synthetic analysis window | PASS | Derived creation bound retains observable overlapping timeslices; slot usage is not autoscaling billing |
