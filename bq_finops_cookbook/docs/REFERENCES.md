# Reference Library

This file contains additional resources and official documentation links for the BQ FinOps Agent.

## Official Documentation

### Core Concepts
- [BigQuery Reservations Introduction](https://cloud.google.com/bigquery/docs/reservations-intro) - Workload management models and concepts
- [BigQuery Editions](https://cloud.google.com/bigquery/docs/editions-intro) - Understanding Standard, Enterprise, and Enterprise Plus editions
- [Workload Management Best Practices](https://cloud.google.com/bigquery/docs/best-practices-performance-compute) - Performance optimization guidance
- [Workload Management with Reservations](https://cloud.google.com/bigquery/docs/reservations-workload-management) - Detailed reservation configuration guide

### Autoscaling and Slots
- [Autoscaling Best Practices](https://cloud.google.com/bigquery/docs/slots#autoscaling_best_practices) - Billing behavior, 1-minute minimum, scaled-vs-used billing
- [Use Autoscaling Reservations](https://cloud.google.com/bigquery/docs/slots#use_autoscaling_reservations) - Autoscaling configuration and billing details

### Pricing
- [BigQuery Pricing](https://cloud.google.com/bigquery/pricing) - On-demand and edition pricing details
- [Data Ingestion Pricing](https://cloud.google.com/bigquery/pricing#data_ingestion_pricing) - Streaming insert and Storage Write API pricing
- [Capacity Compute Pricing](https://cloud.google.com/bigquery/pricing#capacity_compute_analysis_pricing) - Slot-hour pricing by edition

### Quotas and Limits
- [Query Job Quotas](https://cloud.google.com/bigquery/quotas#query_jobs) - Queue limits (1,000 interactive queries per project per region)
- [API Request Quotas](https://cloud.google.com/bigquery/quotas#api_request_quotas) - 100 req/s per user per method
- [Query Queues and Limitations](https://cloud.google.com/bigquery/docs/query-queues#limitations) - Queue behavior and hard limits
- [Troubleshoot Quotas](https://cloud.google.com/bigquery/docs/troubleshoot-quotas) - Resolution strategies including project distribution

### Streaming and Data Ingestion
- [Storage Write API Introduction](https://cloud.google.com/bigquery/docs/write-api) - Modern gRPC streaming with exactly-once semantics
- [Streaming Data into BigQuery](https://cloud.google.com/bigquery/docs/streaming-data-into-bigquery) - Legacy tabledata.insertAll method
- [BI Engine Introduction](https://cloud.google.com/bigquery/docs/bi-engine-intro) - In-memory analysis for sub-second queries

### INFORMATION_SCHEMA Views
- [INFORMATION_SCHEMA.JOBS View](https://cloud.google.com/bigquery/docs/information-schema-jobs) - Job metadata and query examples
- [INFORMATION_SCHEMA.JOBS_TIMELINE View](https://cloud.google.com/bigquery/docs/information-schema-jobs-timeline) - Time-series slot usage analysis
- [INFORMATION_SCHEMA.RESERVATIONS View](https://cloud.google.com/bigquery/docs/information-schema-reservations) - Reservation configuration and join patterns
- [INFORMATION_SCHEMA.TABLE_STORAGE View](https://cloud.google.com/bigquery/docs/information-schema-table-storage) - Storage consumption analysis
- [INFORMATION_SCHEMA.WRITE_API_TIMELINE View](https://cloud.google.com/bigquery/docs/information-schema-write-api) - Streaming ingestion metrics

## Query Pattern Sources

All SQL queries in this guide are based on official Google Cloud BigQuery documentation:

- **List Reservations (Query 0.1):** [RESERVATIONS view schema](https://cloud.google.com/bigquery/docs/information-schema-reservations)
- **Reservation Assignments (Query 0.2):** [ASSIGNMENTS view](https://cloud.google.com/bigquery/docs/information-schema-assignments)
- **Historical Commitments (Query 0.2a):** Adapted from [bigquery-utils/dashboards/system_tables](https://github.com/GoogleCloudPlatform/bigquery-utils/tree/master/dashboards/system_tables)
- **Current Utilization (Query 0.3):** [Joining reservation views and job views](https://cloud.google.com/bigquery/docs/information-schema-reservations#joining_between_the_reservation_views_and_the_job_views)
- **Percentile Calculation (Query 1.1):** [Match slot usage behavior from administrative resource charts](https://cloud.google.com/bigquery/docs/information-schema-jobs-timeline#match_slot_usage_behavior_from_administrative_resource_charts)
- **Top Consumers (Query 1.2):** [Most expensive queries by project](https://cloud.google.com/bigquery/docs/information-schema-jobs#most_expensive_queries_by_project)
- **Slot Contention (Query 4.1):** [View jobs with slot contention insights](https://cloud.google.com/bigquery/docs/information-schema-jobs#view_jobs_with_slot_contention_insights)
- **Bytes Processed (Query 4.2):** [Bytes processed per user identity](https://cloud.google.com/bigquery/docs/information-schema-jobs#bytes_processed_per_user_identity)
- **Average Slot Utilization:** [Calculate average slot utilization](https://cloud.google.com/bigquery/docs/information-schema-jobs#calculate_average_slot_utilization)
- **Queue Pressure (Query 4.10):** [JOBS_TIMELINE PENDING/RUNNING](https://cloud.google.com/bigquery/docs/information-schema-jobs-timeline#number_of_running_and_pending_jobs_over_time)
- **Streaming Ingestion (Query 5.1):** [WRITE_API_TIMELINE view](https://cloud.google.com/bigquery/docs/information-schema-write-api)
- **Storage Analysis (Query 6.1):** [Table storage view](https://cloud.google.com/bigquery/docs/information-schema-table-storage)

## Command Reference

- [bq command-line tool reference](https://cloud.google.com/bigquery/docs/reference/bq-cli-reference) - CLI commands for reservation management
- [Creating and managing reservations](https://cloud.google.com/bigquery/docs/reservations-workload-management) - Detailed reservation configuration guide

## Cloud Monitoring Metrics

- `bigquery.googleapis.com/storage/uploaded_bytes` - Total bytes ingested via streaming
- `bigquery.googleapis.com/storage/uploaded_bytes_billed` - Billed bytes for billing cross-reference
- [Google Cloud metrics reference](https://cloud.google.com/monitoring/api/metrics_gcp#gcp-bigquery) - Full list of BigQuery metrics
