# Storage & Cost Analysis

> **Synthetic sample:** illustrative fixture only; not current project data or pricing.

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
- Almost 100% of the synthetic logical bytes are long-term. Current location-specific storage prices were not supplied, so no dollar or percentage savings are claimed.
- Table age and long-term status are triage signals, not deletion evidence. Verify ownership, retention, legal hold, dependencies, backups, and recent reads before proposing archival or deletion.

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
- If future high-volume streaming is planned, compare current location-specific ingestion prices and delivery requirements. Storage Write API exactly-once semantics require application-created streams with correctly managed offsets.

## Estimated On-Demand Costs

- **Total Bytes Scanned (30d):** 405,978,646 bytes (~0.0004 TiB)
- **Estimated Cost:** NOT VERIFIED (location-specific price not supplied)
- **Top Principal:** synthetic fingerprint `9d5e…` (150 queries)
