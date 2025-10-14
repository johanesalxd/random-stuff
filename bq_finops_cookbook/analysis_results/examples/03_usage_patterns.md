# Usage Patterns (30-Day Analysis)

**Project:** your-project-id
**Region:** US
**Analysis Period:** Last 30 days
**Analysis Date:** October 14, 2025

## Peak Usage Hours

Peak usage occurs primarily on Mondays and Tuesdays during early morning hours (Singapore/Asia timezone):

| Rank | Day of Week | Hour (UTC) | Avg Slot-Seconds | Max Slot-Seconds |
|------|-------------|-----------|------------------|------------------|
| 1 | Monday (2) | 02:00 | 807.4 | 2000.0 |
| 2 | Monday (2) | 03:00 | 761.0 | 2000.0 |
| 3 | Sunday (1) | 07:00 | 590.5 | 2000.0 |
| 4 | Monday (2) | 04:00 | 437.9 | 923.0 |
| 5 | Saturday (7) | 18:00 | 98.6 | 518.9 |

**Note:** Day of week: 1=Sunday, 2=Monday, 3=Tuesday, 4=Wednesday, 5=Thursday, 6=Friday, 7=Saturday

## Peak Analysis

- **Primary Peak:** Monday 02:00-04:00 UTC (10:00 AM - 12:00 PM Singapore time)
- **Secondary Peak:** Sunday 07:00 UTC (3:00 PM Singapore time)
- **Tertiary Peak:** Saturday 18:00-20:00 UTC (2:00 AM - 4:00 AM Singapore time next day)

## Off-Peak Hours

Most hours show minimal or zero activity. The workload is highly concentrated in specific time windows.

## Weekly Trends

| Week | Total Slot-Hours | Days in Week | Trend |
|------|-----------------|--------------|-------|
| 37 | 0.0 | 7 | Inactive |
| 38 | 9.6 | 7 | Low activity |
| 39 | 377.6 | 7 | **High activity** ↑ |
| 40 | 0.1 | 7 | Minimal ↓ |
| 41 | 0.1 | 3 | Minimal → |

## Key Observations

1. **Concentrated Activity:** Week 39 accounts for 97% of all slot usage in the 30-day period
2. **Sporadic Pattern:** Most weeks show near-zero activity with one week of intense usage
3. **Time Zone Alignment:** Peak hours align with Singapore business hours (10 AM - 12 PM)
4. **Weekend Activity:** Some activity on weekends suggests batch processing or ad-hoc analysis

## Scheduling Recommendations

Given the sporadic nature of this workload:

1. **No Scheduled Optimization Needed:** The workload is too unpredictable for scheduled batch windows
2. **On-Demand Suitable:** The irregular pattern makes on-demand pricing most cost-effective
3. **Monitor Week 39 Pattern:** If this represents a monthly reporting cycle, consider scheduling similar workloads during off-peak hours in future months
4. **Potential Batch Window:** If regular batch jobs are needed, consider scheduling during UTC 00:00-02:00 (8:00-10:00 AM Singapore) when current usage is minimal
