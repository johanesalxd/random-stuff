# BigQuery FinOps Analyst for Antigravity

A read-only BigQuery capacity, workload, storage, and cost-analysis skill designed for **Antigravity CLI with Gemini 3.5 Flash with thinking set to High**.

The cookbook uses BigQuery MCP tools first, falls back to read-only `bq query`/metadata inspection when necessary, and writes seven structured Markdown reports. It never changes reservations, assignments, commitments, or dataset billing configuration.

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
| `PROPOSED` | Human-reviewed action that was not executed |

Pricing is **not embedded as timeless truth**. Supply and cite current location-specific prices before producing dollar savings. Without verified prices, the analyst provides capacity guidance and marks savings `NOT VERIFIED`.

## Safety boundary

- Cloud execution is strictly read-only.
- MCP is the primary query and metadata path.
- `bq` is a fallback for read-only inspection only.
- Reservation, assignment, commitment, and storage-model commands may appear only as labelled proposals.
- Missing IAM, unsupported fields, empty history, or unavailable recommender data are reported as evidence gaps.
- Raw query text is not included in reports by default; user identities should be pseudonymized unless explicitly authorized.

## Requirements

- Antigravity CLI with Gemini 3.5 Flash with thinking set to High
- A connected BigQuery MCP server
- Google Cloud authentication appropriate to that MCP server
- Target workload project ID
- Exact BigQuery location (`us`, `eu`, `asia-northeast1`, and so on)
- Reservation administration project ID when different from the workload project
- Read permissions for the required `INFORMATION_SCHEMA` views

See [`resources/IAM.md`](.agents/skills/bq-finops-analyst/resources/IAM.md) for the staged access model.

## Install and run

```bash
git clone https://github.com/johanesalxd/random-stuff.git
cd random-stuff/bq_finops_cookbook
agy
```

Inside Antigravity CLI:

1. Run `/skills` and verify `bq-finops-analyst` is listed.
2. Run `/mcp` and verify the BigQuery MCP server is connected.
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
6. Execute read-only SQL through BigQuery MCP.
7. Record every failed/unavailable query and fallback.
8. Generate reports.
9. Run the deterministic decision guardrail before presenting the final strategy.

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
- Implementation Proposals
- Validation Criteria
- Documentation Checks
- MCP / bq Execution Notes
- Next Steps

## Decision guardrails

The CV, percentile, and burst-ratio thresholds are local planning heuristics. They do not override current product limits, pricing, Slot Recommender, Slot Estimator, workload SLOs, or human review.

Important rules:

- A zero median makes `p95 / p50` undefined; do not divide by zero.
- High burstiness with tiny absolute usage does not automatically justify reservations.
- `p25 >= 50` alone does not justify a commitment.
- Standard edition has no baseline slots and is bounded by its current documented maximum reservation size.
- A workload above the current Standard limit must branch to another valid strategy; never emit an invalid Standard command.
- Assigned jobs exceeding available capacity do not automatically spill to on-demand.
- Slot usage is not the same as autoscaling billing.
- Recommender disagreement forces review rather than silent override.

## Contributor verification

The project uses Python standard-library tests only:

```bash
python3 -m unittest discover -s tests -v
python3 scripts/validate_cookbook.py all
python3 scripts/validate_cookbook.py inventory
git diff --check
```

Live metadata smoke tests require an explicitly approved non-production project. Offline green does not imply live GCP validation.

## Source hierarchy

1. Current official Google Cloud documentation and APIs
2. Current official Antigravity documentation
3. Official `GoogleCloudPlatform/bigquery-utils` patterns where applicable
4. Explicitly labelled cookbook heuristics
5. Model synthesis

Start with:

- [Antigravity skills](https://antigravity.google/docs/skills)
- [Antigravity MCP](https://antigravity.google/docs/mcp)
- [BigQuery editions](https://docs.cloud.google.com/bigquery/docs/editions-intro)
- [Workload reservations](https://docs.cloud.google.com/bigquery/docs/reservations-workload-management)
- [Reservation management](https://docs.cloud.google.com/bigquery/docs/reservations-tasks)
- [JOBS_TIMELINE](https://docs.cloud.google.com/bigquery/docs/information-schema-jobs-timeline)
- [Slot estimator](https://docs.cloud.google.com/bigquery/docs/slot-estimator)
- [BigQuery cost best practices](https://docs.cloud.google.com/bigquery/docs/best-practices-costs)

The complete dated source index is in `.agents/skills/bq-finops-analyst/resources/REFERENCES.md`.
