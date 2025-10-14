# Slot Usage Metrics (30-Day Analysis)

**Project:** your-project-id
**Region:** US
**Analysis Period:** Last 30 days
**Analysis Date:** October 14, 2025

## Percentile Distribution

- **p10:** 0.0 slots
- **p25:** 0.0 slots
- **p50:** 0.0 slots (median)
- **p75:** 0.0 slots
- **p95:** 1.4 slots
- **max:** 190.7 slots

## Statistical Summary

- **Average:** 2.7 slots
- **Standard Deviation:** 20.3 slots

## Workload Characterization

### Stability Metric

- **Coefficient of Variation:** 7.52 (stddev 20.3 / avg 2.7)
- **Classification:** Highly Variable
- **Interpretation:** The workload shows extreme variability with a CV > 1.0, indicating highly unpredictable and sporadic usage patterns. Most hours have zero or minimal slot usage, with occasional large spikes.

### Burstiness Metric

- **Burst Ratio (p95/p50):** Undefined (p50 = 0)
- **Peak to Average Ratio (max/avg):** 70.6
- **Classification:** Extremely High Burst
- **Interpretation:** The workload is characterized by long periods of inactivity (50% of hours use 0 slots) followed by occasional very large bursts (max 190.7 slots). This represents a classic sporadic, unpredictable workload pattern.

## Key Observations

1. **Sporadic Usage:** 75% of hours use 0 slots, indicating the project is inactive most of the time
2. **Occasional Large Jobs:** When queries run, they can consume significant resources (up to 190.7 slots)
3. **Low Average Utilization:** Average of only 2.7 slots suggests minimal sustained workload
4. **High Variability:** Standard deviation (20.3) is 7.5x the average, confirming extreme unpredictability
