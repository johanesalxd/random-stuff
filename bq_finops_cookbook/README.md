# BigQuery FinOps Analyst for Antigravity

A read-only BigQuery capacity, workload, storage, and cost-analysis skill designed for **Antigravity CLI with Gemini 3.5 Flash with thinking set to High**.

The cookbook runs read-only `bq`/`gcloud` CLI commands (authenticated with Application Default Credentials) and writes seven structured Markdown reports.

> **This skill is read-only. It only produces analysis and recommendations — it never changes any cloud resource.** Every reservation, assignment, commitment, or storage-billing change is described as a recommendation with a link to the official documentation, for **you** to perform yourself.

## What it analyzes

- Existing reservations, assignments, and commitment history
- 30-day slot distribution and workload concentration
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
| `OFFICIAL` | Current Google Cloud constraint or recommendation |
| `HEURISTIC` | Cookbook planning rule, not a Google product rule |
| `ASSUMPTION` | Price, discount, date, workload window, or missing evidence |
| `RECOMMENDATION` | A documented action for the user to perform themselves; never executed by this skill |

Pricing is **not embedded as timeless truth**. Supply and cite current location-specific prices before producing dollar savings. Without verified prices, the analyst provides capacity guidance and marks savings `NOT VERIFIED`.

## Safety boundary

- Cloud execution is strictly read-only; only `bq query` (SELECT), `bq show`, `bq ls`, and `gcloud ... describe/list` are ever issued.
- The skill never runs a resource-changing command and never emits runnable mutation commands or DDL.
- Reservation, assignment, commitment, and storage-model changes appear only as recommendations with links to official docs, for the user to perform.
- Missing IAM, unsupported fields, empty history, or unavailable recommender data are reported as evidence gaps.
- Raw query text is not included in reports by default; user identities should be pseudonymized unless explicitly authorized.

## Requirements

- Antigravity CLI with Gemini 3.5 Flash with thinking set to High
- `bq` and `gcloud` CLIs authenticated with Application Default Credentials (`gcloud auth application-default login`)
- Target workload project ID
- Exact BigQuery location (`us`, `eu`, `asia-northeast1`, and so on)
- Reservation administration project ID when different from the workload project
- The minimum read-only IAM roles for your ADC identity:
  - `roles/bigquery.jobUser` (run the read-only queries)
  - `roles/bigquery.resourceViewer` (jobs, reservations, assignments, commitments)
  - `roles/bigquery.metadataViewer` (tables, columns, storage, write-API metadata)
  - optional: `roles/bigquery.slotRecommenderViewer` and `roles/billing.viewer` for official Slot Recommender output and dollar figures

See [`resources/IAM.md`](.agents/skills/bq-finops-analyst/resources/IAM.md) for the full role matrix and the roles you must **not** grant.

## Install and run

```bash
git clone https://github.com/johanesalxd/random-stuff.git
cd random-stuff/bq_finops_cookbook
agy
```

Inside Antigravity CLI:

1. Run `/skills` and verify `bq-finops-analyst` is listed.
2. Verify ADC is active: `gcloud auth application-default print-access-token` succeeds and `gcloud config list` shows the expected account.
3. Start the analysis:

```text
Use the bq-finops-analyst skill to analyze workload project PROJECT_ID in LOCATION.
The reservation administration project is ADMIN_PROJECT_ID.
Keep all GCP operations read-only and write reports to analysis_results/.
```

If the workload has no separate administration project, say so explicitly.

## Runtime flow

1. Read `.agents/skills/bq-finops-analyst/SKILL.md`.
2. Read `resources/execution_manifest.json`.
3. Load only the required query sections from `resources/finops_agent.md`.
4. Verify volatile facts through `resources/claim_matrix.json` and current official docs.
5. For broad audits, let the main agent delegate independent product-rule, SQL, and report-review lanes; monitor them with `/agents`. Subagents remain read-only and the main agent verifies their findings.
6. Execute read-only SQL via `bq query`, and read metadata via `bq show`/`bq ls`/`gcloud ... describe/list`.
7. Record every failed/unavailable query and fallback.
8. Generate reports.
9. Apply the deterministic decision rules (see the Decision Logic section of `finops_agent.md`) before presenting the final strategy.

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

## Source hierarchy

1. Current official Google Cloud documentation and APIs
2. Current official Antigravity documentation
3. Official `GoogleCloudPlatform/bigquery-utils` patterns where applicable
4. Explicitly labelled cookbook heuristics
5. Model synthesis

Start with:

- [Antigravity skills](https://antigravity.google/docs/skills)
- [Application Default Credentials](https://docs.cloud.google.com/docs/authentication/application-default-credentials)
- [BigQuery editions](https://docs.cloud.google.com/bigquery/docs/editions-intro)
- [Workload reservations](https://docs.cloud.google.com/bigquery/docs/reservations-workload-management)
- [Reservation management](https://docs.cloud.google.com/bigquery/docs/reservations-tasks)
- [JOBS_TIMELINE](https://docs.cloud.google.com/bigquery/docs/information-schema-jobs-timeline)
- [Slot estimator](https://docs.cloud.google.com/bigquery/docs/slot-estimator)
- [BigQuery cost best practices](https://docs.cloud.google.com/bigquery/docs/best-practices-costs)

The complete dated source index is in `.agents/skills/bq-finops-analyst/resources/REFERENCES.md`.
