# Usage Patterns (30-Day Analysis)

## Peak Usage Hours
- **Primary Peak:** Daily, 09:00 - 11:00 UTC (Morning Reporting) - 2,200 slots
- **Secondary Peak:** Daily, 01:00 UTC (ETL Batch) - 1,500 slots

## Off-Peak Hours
- **Lowest Usage:** 04:00 - 08:00 UTC
- **Recommended Batch Window:** Shift heavy ETL jobs to the 04:00-08:00 window to reduce contention.

## Weekly Trends
- **Trend:** +5% week-over-week growth.
- **Pattern:** Weekdays are 3x busier than weekends.

## Scheduling Recommendations
- **Action:** The "Morning Reporting" spike is causing the p95 to jump. Pre-calculate these reports during the off-peak window (04:00) using dbt or scheduled queries.
