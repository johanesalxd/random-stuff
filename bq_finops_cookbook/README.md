# BigQuery FinOps Analyst for Antigravity

A read-only BigQuery capacity, workload, storage, and cost-analysis skill for
**Antigravity CLI with Gemini 3.5 Flash selected through `/model`**.

The cookbook points the analyst to current official Google Cloud documentation,
runs live analysis through read-only `bq`/`gcloud` CLI operations using gcloud
CLI credentials, and writes seven structured Markdown reports. BigQuery MCP is
not used for live data, and no documentation MCP is required at runtime.

> **This skill is read-only. It only produces analysis and recommendations — it never changes any cloud resource.** Every reservation, assignment, commitment, or storage-billing change is described as a recommendation with a link to the official documentation, for **you** to perform yourself.

## What it analyzes

- Existing reservations, assignments, and commitment history
- Parameterized slot distribution and workload concentration (default: the
  previous 30 complete UTC days)
- Queue pressure, contention, errors, and query-performance insights
- Capacity sensitivity across on-demand and reservation strategies
- Storage footprint, long-term storage, and stale-table triage
- Storage Write API activity and storage-billing sensitivity
- Official Slot Recommender/Slot Estimator evidence when available

## Evidence model

Every final recommendation separates:

| Label | Meaning |
|---|---|
| `OBSERVED` | Direct result from BigQuery metadata |
| `DERIVED` | Deterministic calculation from observed values |
| `OFFICIAL` | Current claim verified against a retrieved first-party page |
| `HEURISTIC` | Cookbook planning rule, not a Google product rule |
| `ASSUMPTION` | Price, discount, date, workload window, or missing evidence |
| `RECOMMENDATION` | A documented action for the user to perform themselves; never executed by this skill |

Pricing is **not embedded as timeless truth**. Supply and cite current location-specific prices before producing dollar savings. Without verified prices, the analyst provides capacity guidance and marks savings `NOT VERIFIED`.

## Safety boundary

- Cloud execution is limited to operations that current official `bq` and
  [gcloud](https://docs.cloud.google.com/sdk/docs/authorizing) documentation
  establishes as read-only.
- Query jobs bind the query project, location, and GoogleSQL mode explicitly;
  destination writes, DDL, and DML are prohibited.
- The skill never runs a resource-changing command and never emits runnable mutation commands or DDL.
- Reservation, assignment, commitment, and storage-model changes appear only as recommendations with links to official docs, for the user to perform.
- Missing IAM, unsupported fields, empty history, or unavailable recommender data are reported as evidence gaps.
- Reports never include raw workload query text, user identities, job IDs, error
  messages, or Query 4.2 table identifiers. Principal, job, and workload-derived
  table fingerprints use a per-run ephemeral salt that is never persisted;
  Google-provided normalized query hashes remain separately labelled. Approved
  configuration identifiers and storage-inventory/dataset-audit resource names
  may appear when needed for scope or actionable metadata analysis. Generic
  recommendation targets and Write API dataset/table identifiers remain
  fingerprinted, and free-form recommendation descriptions are omitted.
  Explicit approval permits other ephemeral diagnosis only, not persistence.

## Requirements

- Antigravity CLI with Gemini 3.5 Flash available through `/model`
- A read-only web or documentation-retrieval capability for first-party claim
  grounding; MCP is optional
- `bq` and `gcloud` CLIs authenticated with an active gcloud CLI account or
  configured service-account impersonation
- A dedicated analysis principal whose effective IAM is verified to exclude
  BigQuery data and resource mutation permissions
- Target workload project ID
- Query project ID that executes and bills the metadata queries
- Both an inclusive analysis start and exclusive analysis end timestamp, or
  neither to accept UTC midnight 30 days ago through the current UTC midnight
- Exact BigQuery location (`us`, `eu`, `asia-northeast1`, and so on)
- Reservation administration project ID when different from the workload project
- The minimum read-only IAM roles at the correct scope:
  - `roles/bigquery.jobUser` on the query project
  - `roles/bigquery.resourceViewer` on workload and reservation administration
    projects as applicable
  - `roles/bigquery.metadataViewer` on workload projects for project-level
    storage/Write API views, and on required datasets for dataset-scoped audits
  - optional: `roles/bigquery.slotRecommenderViewer` and `roles/billing.viewer` for official Slot Recommender output and dollar figures

See [the IAM resource](.agents/skills/bq-finops-analyst/resources/IAM.md) for the
full role matrix and the roles you must **not** grant.

Dataset IDs, BI Engine/Storage Write API scope, recommender/billing access, and
dated prices plus a materiality threshold are
conditional inputs. Their absence makes the associated optional analysis `NOT
APPLICABLE`, unless you explicitly requested that analysis, in which case it is
`BLOCKED`.

One invocation analyzes one workload project. Users may ask Antigravity to run
separate project analyses in parallel, but this cookbook does not aggregate
those runs and always marks Hybrid `INELIGIBLE`.

## Readiness matrix

| Stage | Owner | Check | Failure outcome |
|---|---|---|---|
| One-time setup | User | Launch from this directory; `/skills` discovers the skill; Gemini 3.5 Flash is selected through `/model`; `bq`/`gcloud` are available; a dedicated least-privilege principal exists | Setup or live execution `BLOCKED` |
| Permissions | User | Select `strict` or `request-review` through `/permissions`; configure fine-grained allow/ask/deny rules separately in Antigravity settings or prompts | Live execution `BLOCKED` when read-only enforcement is uncertain |
| Required run inputs | User | Workload project, query project, exact location, administration project or explicit same-project, analysis window, and read-only authorization | Preflight `BLOCKED` before cloud access |
| Documentation | Agent | Retrieve first-party pages through an available read-only web/documentation capability and record retrieval dates | Documentation `GAP`; strategy-changing gaps require `REVIEW_REQUIRED` |
| Automatic preflight | Agent | Identify active/impersonated principal without tokens; validate IAM, APIs/views, project/location bindings, and all 25 applicability outcomes | `BLOCKED_LIVE_EXECUTION` or `INSUFFICIENT_EVIDENCE` |
| Optional evidence | Both | Supply conditional inputs only for requested optional analyses | `READY_WITH_OPTIONAL_GAPS`, `NOT APPLICABLE`, or scoped `BLOCKED` |

Terminal states are `READY`, `READY_WITH_OPTIONAL_GAPS`,
`BLOCKED_LIVE_EXECUTION`, `INSUFFICIENT_EVIDENCE`, and `REVIEW_REQUIRED`.
Even a blocked run produces explicitly scoped report stubs; it never claims a
completed live analysis.

For each optional query, an absent business trigger is `NOT APPLICABLE`; a
present trigger with missing inputs, IAM, APIs, or views is `BLOCKED`; a valid
execution returning zero rows is `PASS`.

## Install and run

```bash
git clone https://github.com/johanesalxd/random-stuff.git
cd random-stuff/bq_finops_cookbook
agy
```

Run `agy` from `bq_finops_cookbook`; launching from the parent repository does
not place this skill under the active workspace root.

Inside Antigravity CLI:

1. Run `/skills` and verify `bq-finops-analyst` is listed.
2. Use `/model` to select Gemini 3.5 Flash.
3. Use `/permissions` to select `strict` or `request-review`. Configure
   fine-grained deny/ask/allow rules separately through Antigravity settings or
   permission prompts, denying operations that current official references
   classify as mutating.
4. Confirm the active or impersonated principal has no effective BigQuery
   data/resource mutation permissions. Terminal rules might not inspect a query
   payload, so broader IAM blocks live execution.
5. Verify the active gcloud account and any service-account impersonation using
   the current official authentication documentation. Do
   not print access tokens.
6. Start the analysis:

```text
Use the bq-finops-analyst skill to analyze workload project PROJECT_ID in LOCATION.
Run metadata queries from query project QUERY_PROJECT_ID.
The reservation administration project is ADMIN_PROJECT_ID.
Use analysis window [ANALYSIS_START_TS, ANALYSIS_END_TS), or the default previous 30 complete UTC days.
Keep all GCP operations read-only and write reports to analysis_results/.
```

If the workload has no separate administration project, say so explicitly.

## From launch to report

1. Verify skill discovery, model, permission preset, fine-grained rules, and the dedicated principal.
2. Give the required project/location inputs and only the conditional inputs relevant to the requested analysis.
3. Let the agent retrieve current first-party documentation and publish the planned status for all 25 queries.
4. Let the agent construct current read-only `bq`/`gcloud` syntax from the linked official references and collect evidence.
5. Review product-rule, SQL, and report subagents through `/agents`; use `/tasks` to monitor active background shell processes.
6. Receive seven reports with explicit evidence, scope, gaps, user-executed recommendations, and no cloud mutation.

## Runtime flow

1. Read `.agents/skills/bq-finops-analyst/SKILL.md`.
2. Read `.agents/skills/bq-finops-analyst/resources/execution_manifest.json`.
3. Load only the required query sections from
   `.agents/skills/bq-finops-analyst/resources/finops_agent.md`.
4. Retrieve and verify volatile facts against the first-party URLs in
   `.agents/skills/bq-finops-analyst/resources/claim_matrix.json` using whatever
   read-only documentation or web capability is available. MCP is optional.
5. Define read-only product-rule, SQL, and report-review subagents; disable write
   tools, instruct them not to delegate further, monitor them with `/agents`, and
   reconcile their `PASS`/`GAP` results in the main agent. Treat non-delegation as
   behavioral policy unless the active runtime exposes an enforcement control.
6. From the linked current official references, construct the current CLI
   syntax that satisfies the semantic contract: explicit query project,
   location, GoogleSQL, read-only SQL, and metadata-only inspection.
7. Record every failed/unavailable query and fallback.
8. Generate reports.
9. Apply the deterministic decision rules (see the Decision Logic section of `finops_agent.md`) before presenting the final strategy.

An inability to retrieve a required first-party page is a documentation `GAP`,
regardless of retrieval mechanism. A strategy-changing gap returns
`REVIEW_REQUIRED`; an unverified price prevents dollar estimates.

## Reports

```text
analysis_results/
├── 00_current_configuration.md
├── 01_slot_metrics.md
├── 02_top_consumers.md
├── 03_usage_patterns.md
├── 04_optimization_opportunities.md
├── 05_storage_and_cost.md
└── 06_final_recommendation.md
```

`00_current_configuration.md` is still produced when no reservations exist; it records the observed absence and evidence scope instead of disappearing silently.

`02_top_consumers.md` is a compatibility filename. Its content is
project-scoped workload consumption and must never be interpreted as a
cross-project ranking.

See the [historical parity ledger](.agents/skills/bq-finops-analyst/resources/HISTORICAL_PARITY.md)
for the disposition of every query and retired behavior from commit
`6a6cefeeccb38ec6378204ead31dee76168503fa`.

Every report contains a `Documentation Checks` table with the claim, first-party
URL, retrieval date, applicable scope, `PASS`/`GAP`, and reconciliation note.

The final report must include:

- Current State Summary
- Evidence Quality
- Recommended Strategy
- Alternative Analysis
- Optimization Actions
- Recommended Actions (User-Executed)
- Validation Criteria
- Documentation Checks
- bq / gcloud Execution Notes
- Next Steps

## Decision guardrails

The CV, percentile, and burst-ratio thresholds are local planning heuristics. They do not override current product limits, pricing, Slot Recommender, Slot Estimator, workload SLOs, or human review.

Important rules:

- A zero median makes `p95 / p50` undefined; do not divide by zero.
- High burstiness with tiny absolute usage does not automatically justify reservations.
- `p25 >= 50` alone does not justify a commitment.
- Standard edition has no baseline slots and is bounded by its current documented maximum reservation size.
- A workload above the current Standard limit must branch to another valid strategy; never recommend an invalid Standard size.
- Assigned jobs exceeding available capacity do not automatically spill to on-demand.
- Slot usage is not the same as autoscaling billing.
- Recommender disagreement forces review rather than silent override.
- Hybrid is always `INELIGIBLE` because one invocation analyzes one workload
  project and this version does not aggregate parallel runs.

## Source hierarchy

1. Current official Google Cloud documentation and APIs
2. Current official Antigravity documentation
3. Official `GoogleCloudPlatform/bigquery-utils` patterns where applicable
4. Explicitly labelled cookbook heuristics
5. Model synthesis

Start with:

- [Antigravity skills](https://antigravity.google/docs/skills)
- [Antigravity MCP](https://antigravity.google/docs/mcp)
- [Antigravity CLI reference](https://antigravity.google/docs/cli-reference)
- [Antigravity permissions](https://www.antigravity.google/docs/cli-permissions)
- [Antigravity subagents](https://antigravity.google/docs/cli-subagents)
- [`bq` CLI reference](https://docs.cloud.google.com/bigquery/docs/reference/bq-cli-reference)
- [Run BigQuery queries](https://docs.cloud.google.com/bigquery/docs/running-queries)
- [Authenticate to BigQuery](https://docs.cloud.google.com/bigquery/docs/authentication)
- [gcloud CLI credentials and ADC](https://docs.cloud.google.com/docs/authentication/provide-credentials-adc)
- [BigQuery editions](https://docs.cloud.google.com/bigquery/docs/editions-intro)
- [Workload reservations](https://docs.cloud.google.com/bigquery/docs/reservations-workload-management)
- [Reservation management](https://docs.cloud.google.com/bigquery/docs/reservations-tasks)
- [JOBS_TIMELINE](https://docs.cloud.google.com/bigquery/docs/information-schema-jobs-timeline)
- [Slot estimator](https://docs.cloud.google.com/bigquery/docs/slot-estimator)
- [BigQuery cost best practices](https://docs.cloud.google.com/bigquery/docs/best-practices-costs)

The complete dated source index is in `.agents/skills/bq-finops-analyst/resources/REFERENCES.md`.
