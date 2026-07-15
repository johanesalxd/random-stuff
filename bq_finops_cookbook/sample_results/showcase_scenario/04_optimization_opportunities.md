# Optimization Opportunities (30-Day Analysis)

> **Synthetic sample:** illustrative fixture only; not current project data or pricing.

## Slot Contention
- **Jobs with Contention:** 450 jobs (>10 min wait time)
- **Impact:** Critical morning reports are being delayed by up to 15 minutes during the 9AM spike.

## Job Error Analysis
| Error Reason | Count | % | Diagnosis Status |
|--------------|-------|---|------------------|
| rateLimitExceeded | 12 | 0.1% | REQUIRES_DIAGNOSIS |
| resourcesExceeded | 5 | 0.0% | REQUIRES_DIAGNOSIS |

## Expensive Queries
*Top synthetic principals by TiB processed. Pricing was not verified, so no dollar estimate is shown.*

| Principal | Query Count | TiB Scanned | Avg GiB/Query |
|-----------|------------|-------------|---------------|
| principal `7fa1…` | 15,000 | 500 | 33.0 |
| principal `0bc4…` | 200 | 150 | 750.0 |

**Recommendations:**
- **Partitioning:** The `data-eng` queries scan 750GB avg. Ensure `events_log` table is partitioned by date.
- **BI Dashboard:** The BI tool is scanning too much data. Switch to a summarized/aggregated table for the dashboard.

## Job Impact Analysis
*If we committed to the **Average (520 slots)**:*
- **Jobs Above Threshold:** 35% had per-job average slots above 520; this does not model reservation concurrency or imply on-demand spillover.
- **Impact:** Significant performance degradation during morning peaks.
