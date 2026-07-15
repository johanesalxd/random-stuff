# Storage & Cost Analysis

> **Synthetic sample:** illustrative fixture only; not current project data or pricing.

- **Analysis Window:** [2026-05-05T00:00:00Z, 2026-06-04T00:00:00Z)

Unless labelled otherwise, fixture query rows are OBSERVED, calculations are
DERIVED, interpretations are HEURISTIC, and proposed actions are RECOMMENDATION.

## Top Storage Consumers

| Table | Total Size (GiB) | Active (GiB) | Long Term (GiB) | % Long Term |
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

## Physical Storage Evidence

- **Total Physical:** 208.40 GiB (synthetic; excludes fail-safe)
- **Fail-Safe Physical:** 1.60 GiB (synthetic)
- **Physical Plus Fail-Safe:** 210.00 GiB (synthetic)

## Potential Cleanup Candidates (Created > 90 days ago)

| Table | Created | Size (GiB) |
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

## Storage Write API Activity

No active high-volume streaming was detected in the project:

- **Table Fingerprint:** `0d7c…`
- **Total Requests:** 4
- **Total Rows:** 16
- **Input Bytes:** 16,378 bytes (~16 KiB)
- **Error Requests:** 4 (100% error rate on this specific table)

**Recommendations:**
- Investigate the errors through explicitly approved ephemeral job/API evidence; the aggregate error count does not establish schema, IAM, or another root cause.
- If future high-volume streaming is planned, compare current location-specific ingestion prices and delivery requirements. Storage Write API exactly-once semantics require application-created streams with correctly managed offsets.

## On-Demand Billing Evidence

- **Total Bytes Processed (declared analysis window):** 405,978,646 bytes (~0.0004 TiB)
- **Null-Reservation Bytes Billed:** ~0.0004 TiB (`OBSERVED` synthetic fixture)
- **Estimated Cost:** NOT VERIFIED (location-specific price not supplied)
- **Top Principal Fingerprint:** `9d5e…` (146 queries)
- **Economic Decision Status:** REVIEW_REQUIRED

## Storage Billing Model Sensitivity

- **Status:** NOT APPLICABLE
- **Materiality Threshold:** not supplied
- **Lower-Forecast Candidate:** not produced
- **Billing and Storage-Semantics Reconciliation:** REVIEW_REQUIRED if this analysis is later requested
- **Findings:** No Logical-versus-Physical dollar comparison was requested or produced.

## Query Status

| Query | Status | Evidence / Fallback | Scope or Blocking Note |
|---|---|---|---|
| 5.1 | PASS | Synthetic primary result | Tiny Storage Write API activity; no legacy insertAll inference |
| 6.1 | PASS | Synthetic primary result | Logical, physical, and fail-safe values remain separate |
| 6.2 | PASS | Synthetic primary result | Age-based review candidates only |
| 6.3 | NOT APPLICABLE | Not run | No price inputs, threshold, or requested model comparison |

## Documentation Checks

| Claim | Source URL | Retrieved | Scope | PASS/GAP | Note |
|---|---|---|---|---|---|
| Storage billing forecast | https://docs.cloud.google.com/bigquery/docs/information-schema-table-storage#forecast_storage_billing | 2026-07-15 | Synthetic storage fixture | PASS | Numeric prices remain unverified runtime inputs |
