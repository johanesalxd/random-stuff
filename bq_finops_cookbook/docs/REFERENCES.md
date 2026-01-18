# Reference Library

This file contains additional resources and official documentation links for the BQ FinOps Agent.

## Official Documentation

- [BigQuery Reservations Introduction](https://cloud.google.com/bigquery/docs/reservations-intro) - Workload management models and concepts
- [INFORMATION_SCHEMA.JOBS View](https://cloud.google.com/bigquery/docs/information-schema-jobs) - Job metadata and query examples
- [INFORMATION_SCHEMA.JOBS_TIMELINE View](https://cloud.google.com/bigquery/docs/information-schema-jobs-timeline) - Time-series slot usage analysis
- [Workload Management Best Practices](https://cloud.google.com/bigquery/docs/best-practices-performance-compute) - Performance optimization guidance
- [BigQuery Editions](https://cloud.google.com/bigquery/docs/editions-intro) - Understanding Standard, Enterprise, and Enterprise Plus editions
- [INFORMATION_SCHEMA.TABLE_STORAGE View](https://cloud.google.com/bigquery/docs/information-schema-table-storage) - Storage consumption analysis
- [BigQuery Pricing](https://cloud.google.com/bigquery/pricing) - On-demand and edition pricing details

## Query Pattern Sources

All SQL queries in this guide are based on official Google Cloud BigQuery documentation:

- **Percentile Calculation (Query 1.1):** [Match slot usage behavior from administrative resource charts](https://cloud.google.com/bigquery/docs/information-schema-jobs-timeline#match_slot_usage_behavior_from_administrative_resource_charts)
- **Top Consumers (Query 1.2):** [Most expensive queries by project](https://cloud.google.com/bigquery/docs/information-schema-jobs#most_expensive_queries_by_project)
- **Slot Contention (Query 4.1):** [View jobs with slot contention insights](https://cloud.google.com/bigquery/docs/information-schema-jobs#view_jobs_with_slot_contention_insights)
- **Bytes Processed (Query 4.2):** [Bytes processed per user identity](https://cloud.google.com/bigquery/docs/information-schema-jobs#bytes_processed_per_user_identity)
- **Average Slot Utilization:** [Calculate average slot utilization](https://cloud.google.com/bigquery/docs/information-schema-jobs#calculate_average_slot_utilization)
- **Storage Analysis (Query 6.1):** [Table storage view](https://cloud.google.com/bigquery/docs/information-schema-table-storage)

## Command Reference

- [bq command-line tool reference](https://cloud.google.com/bigquery/docs/reference/bq-cli-reference) - CLI commands for reservation management
- [Creating and managing reservations](https://cloud.google.com/bigquery/docs/reservations-workload-management) - Detailed reservation configuration guide
