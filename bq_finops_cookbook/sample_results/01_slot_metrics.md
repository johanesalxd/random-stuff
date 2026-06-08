# Slot Usage Metrics (30-Day Analysis)

## Percentile Distribution

- **p10:** 0.0005 slots
- **p25:** 0.0006 slots
- **p50:** 0.0007 slots (median)
- **p75:** 0.0008 slots
- **p95:** 0.0019 slots
- **max:** 0.1443 slots

## Statistical Summary

- **Average:** 0.0028 slots
- **Standard Deviation:** 0.0151 slots

## Workload Characterization

### Stability Metric

- **Coefficient of Variation:** 5.39
- **Classification:** Highly variable
- **Interpretation:** The workload exhibits extremely high relative variability because it consists of brief, sporadic user queries and scheduled loads separated by long periods of near-total idle time.

### Burstiness Metric

- **Burst Ratio (p95/p50):** 2.71
- **Classification:** Medium burst
- **Interpretation:** The workload has a moderate level of burstiness when actively executing, with p95 usage sitting at 2.71x the median level. However, the absolute slot requirements are extremely low across all percentiles.
