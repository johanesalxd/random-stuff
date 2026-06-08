# Storage & Cost Analysis

## Top Storage Consumers

| Table | Total Size (GB) | Active (GB) | Long Term (GB) | % Long Term |
|-------|-----------------|-------------|----------------|-------------|
| mdm_demo.customers_standardized | 136.33 | 0.00 | 136.33 | 100.0% |
| mdm_demo.customers_with_embeddings | 135.66 | 0.00 | 135.66 | 100.0% |
| mdm_demo.raw_customers_combined_scale_max | 96.77 | 0.00 | 96.77 | 100.0% |
| cq_demo.taxi_events | 64.35 | 0.00 | 64.35 | 100.0% |
| demo_dataset.ggl633_events | 63.80 | 0.00 | 63.80 | 100.0% |
| gcp_internal.cloud_pricing_export | 43.98 | 5.32 | 38.65 | 87.9% |
| mdm_demo.raw_crm_customers_scale_max | 40.66 | 0.00 | 40.66 | 100.0% |
| mdm_demo.raw_ecommerce_customers_scale_max | 36.99 | 0.00 | 36.99 | 100.0% |
| mdm_demo.raw_erp_customers_scale_max | 31.20 | 0.00 | 31.20 | 100.0% |
| demo_dataset.taxi_events_json | 28.90 | 0.00 | 28.90 | 100.0% |

**Recommendation:**
- Almost 100% of the storage in this project is long-term storage (older than 90 days without modifications), which automatically qualifies for a 50% discount on storage pricing ($0.01 per GB logical instead of $0.02).
- Tables like `mdm_demo.customers_standardized` and `mdm_demo.customers_with_embeddings` should be evaluated. Since they have 100% long-term storage and are not actively being queried, they can be deleted, archived to Google Cloud Storage (Coldline/Archive class), or compressed if they are no longer needed.

## Potential Cleanup Candidates (Created > 90 days ago)

| Table | Created | Size (GB) |
|-------|---------|-----------|
| mdm_demo.customers_with_embeddings | 2025-09-29 | 107.69 |
| mdm_demo.customers_standardized | 2025-09-29 | 107.68 |
| mdm_demo.raw_customers_combined_scale_max | 2025-09-29 | 75.11 |
| demo_dataset.ggl633_events | 2024-09-25 | 59.83 |
| cq_demo.taxi_events | 2024-08-19 | 55.39 |
| gcp_internal.cloud_pricing_export | 2022-01-27 | 41.92 |
| mdm_demo.raw_crm_customers_scale_max | 2025-09-28 | 32.16 |
| mdm_demo.raw_ecommerce_customers_scale_max | 2025-09-28 | 28.91 |
| demo_dataset.taxi_events_json | 2026-01-22 | 24.82 |
| mdm_demo.raw_erp_customers_scale_max | 2025-09-28 | 24.40 |

## Streaming Ingestion

No active high-volume streaming was detected in the project:

- **Table:** `dlp_result_210923`
- **Total Requests:** 4
- **Total Rows:** 16
- **Input Bytes:** 16,378 bytes (~16 KiB)
- **Error Requests:** 4 (100% error rate on this specific table)

**Recommendations:**
- The errors on `dlp_result_210923` should be investigated in the application writing to it (e.g. check schema compatibility or IAM writer permissions).
- If any future high-volume streaming workloads are planned, ensure they use the modern **Storage Write API** instead of legacy `tabledata.insertAll` to save 50% on ingestion costs ($0.025/GiB vs $0.05/GiB).

## Estimated On-Demand Costs

- **Total Bytes Scanned (30d):** 405,978,646 bytes (~0.0004 TiB)
- **Estimated Cost:** $0.0023 USD (at $6.25/TiB standard US on-demand rate)
- **Top Spender:** `admin@example.com` (~$0.0021 USD for 150 queries)
