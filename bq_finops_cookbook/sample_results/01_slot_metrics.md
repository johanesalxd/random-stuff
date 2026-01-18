# Slot Usage Metrics (30-Day Analysis)

## Percentile Distribution
- **p10:** 0.0 slots
- **p25:** 0.0 slots
- **p50:** 0.0 slots (median)
- **p75:** 0.0 slots
- **p95:** 1.4 slots
- **max:** 190.7 slots

## Statistical Summary
- **Average:** 2.7 slots
- **Standard Deviation:** 20.2 slots

## Workload Characterization

### Stability Metric
- **Coefficient of Variation:** 7.48
- **Classification:** Highly Variable
- **Interpretation:** The workload is extremely unstable, with a standard deviation many times larger than the average. This indicates sporadic, high-impact jobs rather than a steady-state workload.

### Burstiness Metric
- **Burst Ratio (p95/p50):** Not applicable (division by zero)
- **Classification:** High burst
- **Interpretation:** The median usage is zero, while the 95th percentile is 1.4 slots and the max is 190.7. This signifies a workload that is idle most of the time but experiences significant, infrequent bursts.
