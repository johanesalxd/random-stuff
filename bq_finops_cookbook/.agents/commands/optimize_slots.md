---
description: OpenCode workflow for BigQuery slot optimization analysis and actionable reservation recommendations
argument-hint: <project_id> <region>
---

# BigQuery Slot Optimization Workflow

Use this command with OpenCode running Gemini 3.5 Flash (`gemini-3.5-flash`) to analyze BigQuery slot usage and recommend the safest workload management strategy: on-demand, reservations, autoscaling reservations, or hybrid.

## Usage

Ask OpenCode:

```markdown
Follow the workflow in .agents/commands/optimize_slots.md to analyze project <PROJECT_ID> in <REGION>.
Use Gemini 3.5 Flash (`gemini-3.5-flash`), keep execution MCP-first, and only fall back to the bq CLI when MCP tools are unavailable or insufficient.
```

Example:

```markdown
Follow the workflow in .agents/commands/optimize_slots.md to analyze project my-gcp-project in region-us.
Use Gemini 3.5 Flash (`gemini-3.5-flash`), keep execution MCP-first, and only fall back to the bq CLI when MCP tools are unavailable or insufficient.
```

## Inputs

- `project_id` (required): GCP project ID where BigQuery compute occurs.
- `region` (required): BigQuery region, formatted for `INFORMATION_SCHEMA` queries as `region-<REGION>`; examples: `region-us`, `region-eu`, `region-asia-northeast1`.

## Required Execution Model

1. Run in OpenCode with Gemini 3.5 Flash (`gemini-3.5-flash`).
2. Read `.agents/agents/finops_agent.md` before querying.
3. Read `docs/REFERENCES.md` before generating implementation commands.
4. Execute SQL through BigQuery MCP tools first:
   - Prefer MCP `execute_sql` for analysis queries.
   - Prefer MCP metadata/table-inspection tools before guessing schemas.
5. Use the `bq` CLI only as fallback when MCP is unavailable, missing a required operation, or returning insufficient diagnostics.
6. Never create, update, delete, or assign reservations during analysis. The workflow may generate proposed commands only.

## Safety Rules

- Treat this as read-only unless the user explicitly asks for implementation after reviewing the reports.
- Do not run destructive commands (`bq rm`, reservation deletion, assignment deletion, or edition migration) without explicit confirmation.
- Do not assume BigQuery product behavior from memory when it affects cost, reservation sizing, edition choice, assignment scope, queueing, autoscaling, or implementation commands.
- Source-check ambiguous behavior against official Google Cloud documentation before writing the final recommendation.
- If live documentation conflicts with prompt instructions or sample output, follow the documentation and cite the conflict in `06_final_recommendation.md`.
- Preserve project IDs, user emails, and query text only when needed for analysis; avoid copying unnecessary sensitive query payloads into reports.

## Source-Backed Documentation Checks

Before writing `06_final_recommendation.md`, verify these product behaviors against official Google Cloud docs linked from `docs/REFERENCES.md` or freshly retrieved docs:

1. Edition constraints:
   - Whether Standard edition supports baseline slots / `slot_capacity`.
   - Current Standard edition reservation size limits.
   - Assignment constraints such as project-only assignment support.
2. Reservation behavior:
   - Whether work above reservation capacity queues, uses idle/autoscale capacity, or falls back to on-demand.
   - Whether assigned jobs spill to on-demand automatically when a reservation is saturated.
3. Autoscaling billing:
   - Autoscaled slots are billed as scaled capacity, with documented rounding/minimums, not exact consumed slot-ms.
4. CLI syntax:
   - Current `bq mk --reservation` flags for baseline slots, autoscale slots, `--max_slots`, and `--scaling_mode`.
   - Do not combine mutually exclusive flags such as `--autoscale_max_slots` with `--max_slots` / `--scaling_mode` unless current docs say this changed.
5. INFORMATION_SCHEMA availability:
   - Confirm view names, region qualifiers, fields, and fallback query variants when a field is optional or version-dependent.

Record the source URLs or doc names used for these checks in `06_final_recommendation.md` under a `Documentation Checks` section.

## Workflow

### Step 1: Initialize Context

OpenCode should load the detailed agent instructions as context:

```markdown
Read .agents/agents/finops_agent.md and execute its complete 6-step analysis process for:
- Project ID: <PROJECT_ID>
- Region: <REGION>

Generate all reports in analysis_results/.
Use MCP BigQuery tools first for SQL execution and metadata checks. If MCP is unavailable or insufficient, use bq CLI fallback commands and note the fallback in the relevant report.
Before final recommendations, verify ambiguous BigQuery reservation, autoscaling, edition, and CLI behavior with official Google Cloud docs.
```

### Step 2: Assess Current Configuration

Run the current-configuration queries from `.agents/agents/finops_agent.md`:

1. Existing reservations.
2. Reservation assignments.
3. Historical commitments.
4. Current utilization.
5. Idle slots.
6. On-demand / unassigned workload indicators.

If a query fails due to an INFORMATION_SCHEMA field mismatch, inspect the view schema through MCP metadata tools or `bq show --schema`, then use the documented fallback query.

### Step 3: Analyze Slot Metrics

Run the slot usage, percentile, top consumer, and pattern queries from `.agents/agents/finops_agent.md`.

Calculate:

- Average slots.
- p50 / p75 / p95 / max slots.
- Coefficient of variation.
- Burst ratio.
- Queue pressure and slot contention signals.

### Step 4: Identify Optimization Opportunities

Evaluate:

- Expensive queries and users.
- Slow queries.
- Jobs with slot contention.
- Pending job / queue pressure windows.
- Storage cost and streaming ingestion cost drivers.
- Whether workload changes, scheduling, query tuning, or reservation changes are the safest first move.

### Step 5: Generate Recommendation

Choose the strategy only after the documentation checks are complete:

- Keep on-demand when usage is low, spiky, or reservation waste would dominate.
- Recommend autoscaling reservations when sustained baseline plus bursts justify capacity pricing.
- Recommend baseline / committed reservations only when stable utilization is high enough to offset commitment and operational risk.
- Recommend hybrid only when the project mix or assignment boundaries support it.

Implementation commands must be proposals, not executed actions. For each proposed command, include:

- Required IAM role or permission.
- Admin project vs workload project distinction.
- Region/location.
- Edition-specific constraints.
- Source-backed note for any non-obvious flag.

### Step 6: Generate Reports

Write reports to `analysis_results/`:

1. `00_current_configuration.md` (if reservations or assignments exist)
2. `01_slot_metrics.md`
3. `02_top_consumers.md`
4. `03_usage_patterns.md`
5. `04_optimization_opportunities.md`
6. `05_storage_and_cost.md`
7. `06_final_recommendation.md`

`06_final_recommendation.md` must include:

- Executive summary.
- Recommended strategy.
- Confidence and key risks.
- Monthly cost estimate assumptions.
- Proposed implementation commands, if any.
- Rollback / validation steps.
- `Documentation Checks` section with official source URLs or document names.
- `MCP / bq Execution Notes` section stating which execution path was used.

## User Presentation

After reports are generated, present this concise summary:

```markdown
Analysis Complete.

Executive Summary:
- Strategy: [Strategy Name]
- Confidence: [High/Medium/Low]
- Key Metric: [e.g., CV = 1.5 indicates high variability]
- Estimated Monthly Spend: [Compute + Storage]
- Execution Path: [MCP-first / bq fallback used]
- Docs Checked: [Yes/No, with source count]

Reports Generated:
1. analysis_results/00_current_configuration.md (if applicable)
2. analysis_results/01_slot_metrics.md
3. analysis_results/02_top_consumers.md
4. analysis_results/03_usage_patterns.md
5. analysis_results/04_optimization_opportunities.md
6. analysis_results/05_storage_and_cost.md
7. analysis_results/06_final_recommendation.md

Next Step:
Review analysis_results/06_final_recommendation.md before running any proposed BigQuery reservation or assignment commands.
```
