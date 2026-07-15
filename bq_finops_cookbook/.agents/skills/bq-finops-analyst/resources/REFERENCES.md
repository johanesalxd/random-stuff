# Official Reference Library

**Last reviewed:** 2026-07-15
**Authority:** Current Google Cloud and Antigravity documentation.
**Policy:** Re-check volatile pricing, quotas, limits, CLI flags, and preview features before every recommendation. `claim_matrix.json` records the dated contract; runtime prices remain explicit inputs.

## Antigravity runtime

- [Agent Skills](https://antigravity.google/docs/skills)
- [Model Context Protocol](https://antigravity.google/docs/mcp)
- [Antigravity CLI overview](https://www.antigravity.google/docs/cli-overview)
- [Background tasks and subagents](https://antigravity.google/docs/cli/subagents)
- [CLI reference](https://antigravity.google/docs/cli-reference)
- [Antigravity models](https://antigravity.google/docs/models)

## BigQuery workload management

- [Introduction to workload management](https://docs.cloud.google.com/bigquery/docs/reservations-intro)
- [Understand reservations](https://docs.cloud.google.com/bigquery/docs/reservations-workload-management)
- [Manage workload reservations](https://docs.cloud.google.com/bigquery/docs/reservations-tasks)
- [Understand BigQuery editions](https://docs.cloud.google.com/bigquery/docs/editions-intro)
- [Understand slots and autoscaling](https://docs.cloud.google.com/bigquery/docs/slots)
- [Estimate slot capacity requirements](https://docs.cloud.google.com/bigquery/docs/slot-estimator)
- [BigQuery Slot Recommender](https://docs.cloud.google.com/bigquery/docs/slot-recommender)
- [Recommender overview](https://docs.cloud.google.com/recommender/docs/overview)

## Pricing and cost controls

- [BigQuery pricing](https://cloud.google.com/bigquery/pricing)
- [BigQuery cost best practices](https://docs.cloud.google.com/bigquery/docs/best-practices-costs)
- [Storage overview and billing models](https://docs.cloud.google.com/bigquery/docs/storage_overview)
- [Forecast storage billing](https://docs.cloud.google.com/bigquery/docs/information-schema-table-storage#forecast_storage_billing)

Do not copy numeric prices into durable runtime instructions. Record location, currency, unit, source URL, and retrieval date in each analysis.

## Quotas and queues

- [BigQuery quotas and limits](https://docs.cloud.google.com/bigquery/quotas)
- [Query queues](https://docs.cloud.google.com/bigquery/docs/query-queues)
- [Troubleshoot quota errors](https://docs.cloud.google.com/bigquery/docs/troubleshoot-quotas)

Error reasons are diagnostic categories. A reason such as `resourcesExceeded` or `quotaExceeded` does not prove a single root cause without message/job context.

## Ingestion

- [Storage Write API](https://docs.cloud.google.com/bigquery/docs/write-api)
- [Storage Write API best practices](https://docs.cloud.google.com/bigquery/docs/write-api-best-practices)
- [Legacy streaming inserts](https://docs.cloud.google.com/bigquery/docs/streaming-data-into-bigquery)
- [Write API `INFORMATION_SCHEMA`](https://docs.cloud.google.com/bigquery/docs/information-schema-write-api)

Exactly-once support requires application-created streams plus correctly managed offsets. Do not claim it for every Storage Write API usage.

## INFORMATION_SCHEMA

- [Introduction to BigQuery `INFORMATION_SCHEMA`](https://docs.cloud.google.com/bigquery/docs/information-schema-intro)
- [JOBS views](https://docs.cloud.google.com/bigquery/docs/information-schema-jobs)
- [JOBS_TIMELINE views](https://docs.cloud.google.com/bigquery/docs/information-schema-jobs-timeline)
- [Reservations](https://docs.cloud.google.com/bigquery/docs/information-schema-reservations)
- [Assignments](https://docs.cloud.google.com/bigquery/docs/information-schema-assignments)
- [Recommendations](https://docs.cloud.google.com/bigquery/docs/information-schema-recommendations)
- [Table storage](https://docs.cloud.google.com/bigquery/docs/information-schema-table-storage)
- [Tables](https://docs.cloud.google.com/bigquery/docs/information-schema-tables)
- [Columns](https://docs.cloud.google.com/bigquery/docs/information-schema-columns)

## Performance

- [Compute performance best practices](https://docs.cloud.google.com/bigquery/docs/best-practices-performance-compute)
- [Query performance insights](https://docs.cloud.google.com/bigquery/docs/query-insights)
- [Administrative resource charts](https://docs.cloud.google.com/bigquery/docs/admin-resource-charts)
- [BI Engine](https://docs.cloud.google.com/bigquery/docs/bi-engine-intro)

## Query pattern sources

- [GoogleCloudPlatform/bigquery-utils system tables](https://github.com/GoogleCloudPlatform/bigquery-utils/tree/master/dashboards/system_tables)
- [GoogleCloudPlatform/bigquery-utils optimization scripts](https://github.com/GoogleCloudPlatform/bigquery-utils/tree/master/scripts/optimization)

Official utility queries are implementation references, not a substitute for checking the current view schema, scope, IAM, pricing, and product limits.

## CLI

- [`bq` command-line reference](https://docs.cloud.google.com/bigquery/docs/reference/bq-cli-reference)
- [Reservation management commands](https://docs.cloud.google.com/bigquery/docs/reservations-tasks)

`--autoscale_max_slots` is mutually exclusive with `--max_slots`/`--scaling_mode`; the latter two are configured together. Re-check preview status and location/edition support before proposing either form.
