# Storage & Cost Analysis

## Top Storage Consumers
*Top tables by total storage size.*

| Table | Total Size | Active | Long Term | % Long Term |
|-------|------------|--------|-----------|-------------|
| `logs.app_events_archive` | 250 TB | 0 TB | 250 TB | 100% |
| `prod.orders` | 45 TB | 45 TB | 0 TB | 0% |
| `staging.test_dump_2024` | 15 TB | 0 TB | 15 TB | 100% |

**Recommendation:**
- **CRITICAL:** `logs.app_events_archive` is consuming **250 TB** of storage and is 100% Long Term (unused for >90 days).
- **Potential Savings:** 250 TB * $0.01/GB = **$2,500/month**.
- **Action:** Move this table to Google Cloud Storage (Archive Class) or set a Partition Expiration to delete data older than 1 year.

## Estimated Monthly Spend (Current)
- **Compute (On-Demand):** ~$8,500
- **Storage:** ~$6,000
- **Total:** ~$14,500 / month

**Optimization Target:**
- **Compute:** Switch to Autoscaling (~$6,000)
- **Storage:** Archive logs (~$2,500 savings)
- **New Total:** ~$9,500 (**$5,000/month savings**)
