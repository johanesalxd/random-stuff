# Usage Patterns (30-Day Analysis)

## Hourly Usage Heatmap (Top Entries)
| Hour | Day | Project | User | Job Type | Avg Slots |
|:--- |:--- |:--- |:--- |:--- |:--- |
| 02:00 | Mon | demo-project | admin@johanesa.altostrat.com | QUERY | 0.04 |
| 01:00 | Mon | demo-project | admin@johanesa.altostrat.com | QUERY | 0.05 |
| 00:00 | Mon | demo-project | admin@johanesa.altostrat.com | QUERY | 0.07 |
| 15:00 | Sat | demo-project | admin@johanesa.altostrat.com | QUERY | 0.01 |
| 14:00 | Sat | demo-project | admin@johanesa.altostrat.com | QUERY | 0.01 |
| 13:00 | Sat | demo-project | admin@johanesa.altostrat.com | QUERY | 0.01 |
| 12:00 | Fri | demo-project | admin@johanesa.altostrat.com | QUERY | 0.19 |

## Observations
*   **Sporadic Activity**: Usage is characterized by very infrequent, low-impact queries.
*   **Primary User**: `admin@johanesa.altostrat.com` is the main driver of the minimal activity observed.
*   **Automated Jobs**: Presence of `bigquery-adminbot` and `service-605626490127...` (Transfer Service) indicates some automated maintenance or data ingestion tasks running in the background, consuming 0 slots (likely simple metadata ops or very fast loads).
