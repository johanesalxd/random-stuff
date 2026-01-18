# Optimization Opportunities (30-Day Analysis)

## Slot Contention
- **Jobs with Contention:** 450 jobs (>10 min wait time)
- **Impact:** Critical morning reports are being delayed by up to 15 minutes during the 9AM spike.

## Job Error Analysis
| Error Reason | Count | % | Capacity-Related |
|--------------|-------|---|------------------|
| rateLimitExceeded | 12 | 0.1% | Yes |
| resourcesExceeded | 5 | 0.0% | Yes |

## Expensive Queries
*Top users by estimated on-demand cost.*

| User | Query Count | TB Scanned | Est. Cost ($) | Avg GB/Query |
|------|------------|------------|---------------|--------------|
| bi-tool@company.com | 15,000 | 500 | $3,125 | 33.0 |
| data-eng@company.com | 200 | 150 | $937 | 750.0 |

**Recommendations:**
- **Partitioning:** The `data-eng` queries scan 750GB avg. Ensure `events_log` table is partitioned by date.
- **BI Dashboard:** The BI tool is scanning too much data. Switch to a summarized/aggregated table for the dashboard.

## Job Impact Analysis
*If we committed to the **Average (520 slots)**:*
- **Jobs Exceeding:** 35% of jobs would need to wait or spill over.
- **Impact:** Significant performance degradation during morning peaks.
