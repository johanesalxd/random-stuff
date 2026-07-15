# Current Configuration Analysis

> **Synthetic sample:** illustrative fixture only; not current project data or pricing.

## Existing Reservations
*No reservations found in project.*

## Current Utilization
- **Reservation:** None (On-Demand)
- **Baseline Slots:** 0
- **Autoscale Max:** N/A
- **Average Utilization:** N/A

## On-Demand Spillover
*100% of queries ran on-demand.*

| Date | Total Queries | On-Demand | Reservation | % On-Demand |
|------|---------------|-----------|-------------|-------------|
| 2026-01-16 | 45,200 | 45,200 | 0 | 100% |
| 2026-01-15 | 42,150 | 42,150 | 0 | 100% |
| 2026-01-14 | 38,900 | 38,900 | 0 | 100% |
| ... | ... | ... | ... | ... |

## Assessment
The project is currently running entirely on the **On-Demand** model. Given the high query volume (avg 40k queries/day), capacity pricing is worth evaluating, but do not assume it is cheaper without comparing current regional on-demand pricing, slot-hour pricing, discounts, and BigQuery recommender output.
