# Official Reference Library

**Last reviewed:** 2026-07-16
**Authority:** Current Google Cloud and Antigravity documentation.
**Policy:** Open the linked first-party pages and re-check volatile pricing,
quotas, limits, schemas, CLI behavior, and preview features before every
recommendation. Repository maintenance prefers Google Developer Knowledge MCP,
then Context7 or official-web retrieval. The Antigravity runtime may use any
available read-only documentation or web capability; MCP is not required.
`claim_matrix.json` records the dated contract, and runtime prices remain
explicit inputs.

## Agentic verification procedure

1. Retrieve the exact first-party page from `cloud.google.com`,
   `docs.cloud.google.com`, or `antigravity.google`; a catalogued link is not
   proof that the claim was checked.
2. Record the retrieval date, target location, edition, CLI version, API state,
   and preview scope that affect the claim.
3. Mark `PASS` only when the page supports the exact value or qualified
   behavior. Mark inaccessible, ambiguous, mismatched, or unsupported claims
   `GAP`.
4. Propagate strategy-changing gaps to `REVIEW_REQUIRED`. Omit dollar estimates
   when a pricing claim is `GAP`.
5. Construct current `bq`/gcloud syntax from the retrieved references; do not
   copy command examples from this repository as durable recipes.

Use this output contract in every final report:

| Claim | Source URL | Retrieved | Scope | PASS/GAP | Note |
|---|---|---|---|---|---|

## Antigravity runtime

- [Agent Skills](https://antigravity.google/docs/skills)
- [CLI plugins and flat skill blueprints](https://antigravity.google/docs/cli-plugins)
- [Antigravity CLI reference](https://antigravity.google/docs/cli-reference)
- [CLI features](https://antigravity.google/docs/cli-features)
- [Subagents and background tasks](https://antigravity.google/docs/cli-subagents)
- [CLI permissions](https://www.antigravity.google/docs/cli-permissions)
- [Model Context Protocol](https://antigravity.google/docs/mcp)
- [Antigravity models](https://antigravity.google/docs/models)

This cookbook uses the nested Agent Skills package documented by the Agent
Skills guide. The CLI plugins guide separately documents flat Markdown skill
blueprints that compile into slash commands; do not conflate the two discovery
shapes.

## Authentication and IAM

- [gcloud CLI authentication](https://docs.cloud.google.com/sdk/docs/authorizing)
- [gcloud CLI credentials are distinct from ADC](https://docs.cloud.google.com/docs/authentication/provide-credentials-adc)
- [`bq` command-line authentication and impersonation](https://docs.cloud.google.com/bigquery/docs/reference/bq-cli-reference)
- [BigQuery access control (predefined roles)](https://docs.cloud.google.com/bigquery/docs/access-control)

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

For timeline windows, `period_start` defines the evidence interval while
`job_creation_time` is the partition key. Derive the earliest observable
overlapping job through `JOBS_BY_PROJECT`; the fixed lookback in an official
example is not a general completeness guarantee. Current JOBS and
JOBS_TIMELINE documentation also warns that history before a project
organization migration can be unavailable; unresolved coverage blocks
full-window timeline conclusions.

- [Reservations](https://docs.cloud.google.com/bigquery/docs/information-schema-reservations)
- [Reservation timeline](https://docs.cloud.google.com/bigquery/docs/information-schema-reservation-timeline)
- [Current capacity commitments](https://docs.cloud.google.com/bigquery/docs/information-schema-capacity-commitments)
- [Capacity commitment changes](https://docs.cloud.google.com/bigquery/docs/information-schema-capacity-commitment-changes)
- [Reservation REST schema](https://docs.cloud.google.com/bigquery/docs/reference/reservations/rest/v1/projects.locations.reservations)
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
- [Run BigQuery queries](https://docs.cloud.google.com/bigquery/docs/running-queries)
- [Authenticate to BigQuery](https://docs.cloud.google.com/bigquery/docs/authentication)
- [Reservation management commands](https://docs.cloud.google.com/bigquery/docs/reservations-tasks)

Use these pages to resolve current syntax and option compatibility. Re-check
preview status and location/edition support before proposing any configuration;
do not preserve a command recipe in the cookbook.
