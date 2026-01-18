# Slot Usage Metrics (30-Day Analysis)

## Percentile Distribution
- **p10:** 150 slots
- **p25:** 280 slots
- **p50:** 450 slots (median)
- **p75:** 850 slots
- **p95:** 1,800 slots
- **max:** 2,400 slots

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
