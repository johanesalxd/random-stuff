# Storage & Cost Analysis

## Top Storage Consumers
| Table | Total Size (GB) | Type | Long Term % |
|:--- |:--- |:--- |:--- |
| `mdm_demo.customers_standardized` | 136.33 | Active/Long Term | 100% |
| `mdm_demo.customers_with_embeddings` | 135.66 | Active/Long Term | 100% |
| `mdm_demo.raw_customers_combined_scale_max` | 96.77 | Active/Long Term | 100% |
| `cq_demo.taxi_events` | 64.35 | Active/Long Term | 95.4% |
| `demo_dataset.ggl633_events` | 63.80 | Active/Long Term | 100% |

## Cleanup Candidates (>90 Days Old)
The following tables are candidates for archival or deletion:

| Table | Created Date | Size (GB) |
|:--- |:--- |:--- |
| `mdm_demo.customers_with_embeddings` | 2025-09-29 | 107.69 |
| `mdm_demo.customers_standardized` | 2025-09-29 | 107.68 |
| `mdm_demo.raw_customers_combined_scale_max` | 2025-09-29 | 75.11 |
| `demo_dataset.ggl633_events` | 2024-09-25 | 59.83 |
| `cq_demo.taxi_events` | 2024-08-19 | 55.39 |

*   **Potential Savings**: Over **400 GB** of storage is sitting in tables created months ago (referencing 2025 dates, implying this environment is simulating a future date or the date extraction logic is relative to a specific context).
*   **Action**: Review the `mdm_demo` and `demo_dataset` tables. If they are static snapshots or demo artifacts, consider deleting them or moving them to a cheaper storage class if not already on long-term pricing.
