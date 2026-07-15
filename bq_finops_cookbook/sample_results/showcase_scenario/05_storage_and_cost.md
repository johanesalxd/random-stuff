# Storage & Cost Analysis

> **Synthetic sample:** illustrative fixture only; not current project data or pricing.

## Top Storage Consumers
*Top tables by total storage size.*

| Table | Total Size | Active | Long Term | % Long Term |
|-------|------------|--------|-----------|-------------|
| `logs.app_events_archive` | 250 TB | 0 TB | 250 TB | 100% |
| `prod.orders` | 45 TB | 45 TB | 0 TB | 0% |
| `staging.test_dump_2024` | 15 TB | 0 TB | 15 TB | 100% |

**Recommendation:**
- **CRITICAL:** `logs.app_events_archive` is consuming **250 TB** of long-term storage. Confirm retention requirements before moving or deleting it.
- **Potential Savings:** Material, but depends on current regional BigQuery storage pricing and any destination storage/retrieval costs.
- **Action:** Consider partition expiration, lifecycle/retention policy changes, or export to cheaper storage only after validating access patterns and compliance needs.

## Estimated Monthly Spend (Current)
- **Compute:** NOT VERIFIED
- **Storage:** NOT VERIFIED
- **Total:** NOT VERIFIED

**Optimization Target:**
- **Compute:** Evaluate Standard Edition autoscaling against actual regional on-demand bytes processed, slot-hour pricing, scaled-slot billing, and recommender output.
- **Storage:** Reduce or tier archive logs where retention policy permits.
- **Expected Outcome:** Potential savings are likely meaningful, but final estimates require current pricing inputs and production validation.
