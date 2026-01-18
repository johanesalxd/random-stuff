# Storage & Cost Analysis

## Top Storage Consumers
*Top tables by total storage size.*

| Table | Total Size (GB) | Active (GB) | Long Term (GB) | % Long Term |
|-------|-----------------|-------------|----------------|-------------|
| mdm_demo.customers_standardized | 136.33 | 0.0 | 136.33 | 100% |
| mdm_demo.customers_with_embeddings | 135.66 | 0.0 | 135.66 | 100% |
| mdm_demo.raw_customers_combined_scale_max | 96.77 | 0.0 | 96.77 | 100% |
| cq_demo.taxi_events | 64.35 | 2.96 | 61.39 | 95.4% |
| demo_dataset.ggl633_events | 63.80 | 0.0 | 63.80 | 100% |

**Recommendation:**
- **Action:** Review `mdm_demo.customers_standardized` (136 GB). It is 100% Long Term storage, meaning it hasn't been modified in 90 days. Consider verifying if it is still needed or can be archived.

## Potential Cleanup Candidates
*Tables created > 90 days ago, sorted by size.*

| Table | Created | Size (GB) |
|-------|---------|-----------|
| mdm_demo.customers_with_embeddings | 2025-09-29 | 107.69 |
| mdm_demo.customers_standardized | 2025-09-29 | 107.68 |
| mdm_demo.raw_customers_combined_scale_max | 2025-09-29 | 75.11 |
| demo_dataset.ggl633_events | 2024-09-25 | 59.83 |
| cq_demo.taxi_events | 2024-08-19 | 55.39 |

## Estimated On-Demand Costs
- **Total Bytes Scanned (30d):** 0.01 TB
- **Estimated Compute Cost:** $0.05
- **Top Spender:** admin@johanesa.altostrat.com
