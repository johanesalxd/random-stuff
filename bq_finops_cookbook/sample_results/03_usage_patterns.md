# Usage Patterns (30-Day Analysis)

## Peak Usage Hours
- **Primary Peak:** Day 2 (Monday), Hour 4 - 190.7 slots
- **Secondary Peak:** Day 2 (Monday), Hour 3 - 150.1 slots
- **Tertiary Peak:** Day 2 (Monday), Hour 2 - 18.2 slots

## Off-Peak Hours
- **Lowest Usage:** The majority of hours show zero slot usage.
- **Recommended Batch Window:** Any time outside of the brief, intense peaks. The most consistently quiet periods are between 20:00 and 01:00 UTC.

## Weekly Trends
| Week | Total Slot-Hours | Days in Week | Trend |
|------|-----------------|--------------|-------|
| 38   | 0.0             | 1            | →     |
| 39   | 377.8           | 7            | ↑     |
| 40   | 9.4             | 7            | ↓     |
| 41   | 0.2             | 2            | ↓     |

## Scheduling Recommendations
- The workload is dominated by a single, major event on Monday, September 29th.
- Most other activity is negligible.
- If the peak event is a recurring batch job, consider optimizing it to reduce its slot footprint. Otherwise, the current on-demand model is appropriate for handling such infrequent, high-demand events.
