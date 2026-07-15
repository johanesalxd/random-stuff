---
name: bq-finops-analyst
description: Performs a source-grounded, read-only BigQuery FinOps analysis covering slot usage, reservations, workload behavior, storage, cost assumptions, and optimization evidence. Use when an Antigravity CLI user asks to assess BigQuery capacity, on-demand versus reservations, query pressure, or storage economics.
---

# BigQuery FinOps Analyst

Target runtime: **Antigravity CLI with Gemini 3.5 Flash with thinking set to High**.

## Inputs

Collect these before querying:

- Workload project ID
- Exact BigQuery location
- Reservation administration project ID, if different
- Analysis window (default: 30 complete days)
- Dataset IDs to inspect for dataset-scoped `INFORMATION_SCHEMA.COLUMNS` audits; do not invent or region-qualify this view
- Whether user identities may be displayed; default is pseudonymized
- Current, dated pricing inputs if dollar estimates are requested
- Confirmation that the target is approved for read-only metadata analysis

Do not infer project, location, administration project, or prices.

## Load order

1. Read `resources/execution_manifest.json`.
2. Read `resources/claim_matrix.json`.
3. Read `resources/IAM.md` and confirm available evidence surfaces.
4. Load only the needed query sections from `resources/finops_agent.md`.
5. Use `resources/REFERENCES.md` to refresh volatile claims from official docs.

This progressive-disclosure order is mandatory for Gemini 3.5 Flash context discipline.

## Non-negotiable guardrails

- **Read-only cloud execution:** Never create, update, resize, assign, purchase, or delete cloud resources.
- **CLI only, read verbs only:** Use `bq` and `gcloud` authenticated with Application Default Credentials (ADC). Only run read commands — `bq query` (SELECT), `bq show`, `bq ls`, `gcloud ... describe`, `gcloud ... list`. Never run `bq mk`, `bq rm`, `bq update`, `bq insert`, `bq cp`, any DDL/DML, or any `gcloud ... create/update/delete`.
- **Never emit executable mutations:** Recommendations are written as prose plus links to official documentation. Do not put runnable resource-changing commands in reports; the user performs any change themselves.
- **Location integrity:** Keep every query and reservation resource in its exact location. Never mix a multi-region and single region.
- **Admin/workload separation:** Reservation metadata often belongs to the administration project; workload jobs belong to workload projects. Record both.
- **No silent gaps:** Missing IAM, unavailable views/fields, empty history, or failed fallbacks must appear in the report.
- **No stale pricing:** If current location-specific prices are not verified, omit dollar savings and mark them `NOT VERIFIED`.
- **No raw query text:** Do not include raw query SQL in reports by default.
- **Identity minimization:** Pseudonymize user emails and job IDs unless the user explicitly authorizes identifiable output.
- **Recommendations, not mutations:** The analysis only produces evidence and recommendations. Any capacity, reservation, assignment, commitment, or storage-billing change is the user's own action, executed outside this skill by following the linked official documentation.

## Evidence labels

Use these labels in every report:

- `OBSERVED` — returned by a read-only metadata query
- `DERIVED` — deterministic calculation from observations
- `OFFICIAL` — current Google Cloud constraint/recommendation
- `HEURISTIC` — cookbook planning rule
- `ASSUMPTION` — price, date, workload, or incomplete evidence
- `RECOMMENDATION` — a documented action for the user to perform themselves; never executed by this skill

## Subagent orchestration

Antigravity CLI can automatically delegate background research and validation. For a broad audit, the main agent may fan out these independent read-only lanes:

1. **Product-rule verifier** — refresh volatile BigQuery claims from first-party Google Cloud documentation.
2. **SQL reviewer** — inspect query scope, fields, units, null/zero handling, and retention limits without running mutations.
3. **Report reviewer** — reconcile evidence labels, sample/report consistency, privacy, and recommendation guardrails.

Rules:

- The main agent owns inputs, evidence reconciliation, and the final answer; subagent summaries are not accepted unverified.
- Give subagents only the tools they need. They run the same read-only `bq`/`gcloud` commands under ADC; never grant or imply cloud-write, reservation mutation, commitment purchase, assignment, deletion, or raw-principal output.
- Use `/agents` to monitor background subagents and inspect pending approvals; use `/tasks` for non-agentic background commands.
- A failed or unavailable subagent is an evidence gap, not permission to guess.

## Execution workflow

### 1. Preflight

- Confirm the selected runtime is Gemini 3.5 Flash with thinking set to **High**; do not run this workflow at a lower thinking level for now.
- Confirm `/skills` discovers this skill.
- Confirm ADC is active and record the identity (`gcloud auth application-default print-access-token` succeeds; `gcloud config list account`).
- Validate project/location strings.
- Confirm only read-only `bq`/`gcloud` commands will be issued for the whole run.
- Record documentation retrieval date.

### 2. Current configuration

Run manifest queries `0.1` through `0.5` as applicable. Always produce `00_current_configuration.md`, including when no reservation exists.

### 3. Workload metrics

Run `1.1` through `1.3`. Compute:

- CV with a zero guard
- Burst ratio with a zero-median guard
- Active-hour and all-hour distributions separately when relevant
- p50, p95, p99, maximum, and zero-usage share

CV and burst thresholds are `HEURISTIC`, never `OFFICIAL`.

### 4. Optimization evidence

Run applicable `4.x` queries. Treat errors as diagnostic categories, not proof of one root cause. Reconcile the cookbook heuristic with Slot Recommender/Slot Estimator when available.

If official and heuristic guidance disagree, return `REVIEW_REQUIRED` and explain both.

### 5. Storage and ingestion

Run applicable `5.1` and `6.x` queries. Keep logical and physical bytes separate. Table age alone is never deletion evidence. Storage Write API exactly-once semantics are conditional on application-created streams with correctly managed offsets.

### 6. Decision guardrail

Before finalizing, apply these deterministic rules (see the Decision Logic section of `resources/finops_agent.md`):

- Insufficient evidence => `INSUFFICIENT_EVIDENCE`
- Standard limit exceeded => never recommend invalid Standard capacity
- Zero median => burst ratio `UNDEFINED`
- Recommender disagreement => `REVIEW_REQUIRED`
- Small absolute use/spend => do not recommend reservations merely because burst ratio is high
- `p25 >= 50` alone => never sufficient for commitment

### 7. Reports

Write:

- `analysis_results/00_current_configuration.md`
- `analysis_results/01_slot_metrics.md`
- `analysis_results/02_top_consumers.md`
- `analysis_results/03_usage_patterns.md`
- `analysis_results/04_optimization_opportunities.md`
- `analysis_results/05_storage_and_cost.md`
- `analysis_results/06_final_recommendation.md`

The final report must contain, in order:

1. Current State Summary
2. Evidence Quality
3. Recommended Strategy
4. Alternative Analysis
5. Optimization Actions
6. Recommended Actions (User-Executed)
7. Validation Criteria
8. Documentation Checks
9. bq / gcloud Execution Notes
10. Next Steps

## Recommended actions, not commands

The analysis never changes cloud resources. Every capacity, reservation, assignment, commitment, or storage-billing recommendation is written as:

- the intended outcome and why the evidence supports it;
- the prechecks, location, administration project, and rollback/lock-in considerations to weigh;
- a link to the official Google Cloud documentation the user follows to perform it.

Do not include runnable resource-changing `bq`/`gcloud` commands or DDL. A storage-billing change is especially sensitive (takes ~24 hours to apply and cannot be changed again for 14 days) and must carry that warning in prose.

## Completion gate

Do not declare the analysis complete unless:

- every required manifest query is `PASS`, `FALLBACK`, `BLOCKED`, or `NOT APPLICABLE`;
- reports agree on metrics and assumptions;
- official constraints are dated and cited;
- pricing is verified or dollar savings are omitted;
- no invalid edition configuration is recommended;
- only read-only `bq`/`gcloud` commands were issued and no GCP resource was changed.
