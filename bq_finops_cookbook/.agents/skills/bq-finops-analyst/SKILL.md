---
name: bq-finops-analyst
description: Performs a source-grounded, read-only BigQuery FinOps analysis covering slot usage, reservations, workload behavior, storage, cost assumptions, and optimization evidence. Use when an Antigravity CLI user asks to assess BigQuery capacity, on-demand versus reservations, query pressure, or storage economics.
---

# BigQuery FinOps Analyst

Target runtime: **Antigravity CLI with Gemini 3.5 Flash selected through `/model`**.

Launch `agy` from the `bq_finops_cookbook` directory. Antigravity discovers this
workspace skill from `<workspace-root>/.agents/skills/bq-finops-analyst/SKILL.md`.

## Inputs

Collect these before querying:

- Workload project ID
- Query project ID that executes and bills the metadata queries
- Exact BigQuery location
- Reservation administration project ID, if different
- Inclusive `analysis_start_ts` and exclusive `analysis_end_ts`; supply both or
  neither. When omitted, set start to UTC midnight 30 days ago and end to the
  current UTC midnight.
- Approved evidence or user confirmation of whether the workload project moved
  into or between organizations during the requested interval. Unknown or
  in-window migration coverage blocks full-window timeline evidence.
- Dataset IDs only when dataset-scoped `INFORMATION_SCHEMA.COLUMNS` auditing is requested
- Confirmation that workload identities, job IDs, workload-derived table
  references, query text, and error messages remain pseudonymized in reports
- Current, dated pricing inputs and a nonnegative materiality threshold if dollar estimates or storage billing sensitivity are requested
- Confirmation that the target is approved for read-only metadata analysis
- Evidence that the active or impersonated analysis principal lacks BigQuery
  data and resource mutation permissions

Do not infer project IDs, location, administration project, or prices.
One invocation analyzes exactly one workload project. A user can orchestrate
parallel invocations for other projects, but this skill does not combine their
evidence or make a cross-project Hybrid recommendation.

## Load order

1. Read `resources/execution_manifest.json`.
2. Read `resources/claim_matrix.json`.
3. Read `resources/IAM.md` and confirm available evidence surfaces.
4. Load only the needed query sections from `resources/finops_agent.md`.
5. Use `resources/REFERENCES.md` to refresh every used volatile claim.

This progressive-disclosure order is a context-discipline requirement for this
skill, not an Antigravity platform requirement.

## Non-negotiable guardrails

- **Separate documentation from data access:** Retrieve current first-party
  documentation with any available read-only documentation or web capability.
  MCP is optional. Use `bq`/`gcloud` CLI, never BigQuery MCP, for live project
  data.
- **Construct current syntax from official references:** Before execution, read
  the current [`bq` CLI reference](https://docs.cloud.google.com/bigquery/docs/reference/bq-cli-reference),
  [query guide](https://docs.cloud.google.com/bigquery/docs/running-queries), and
  [gcloud authentication guide](https://docs.cloud.google.com/sdk/docs/authorizing).
  Do not treat command examples in this repository as durable syntax.
- **Read-only cloud execution:** Run only operations whose current official
  documentation establishes that they inspect metadata or execute read-only
  GoogleSQL. Never use DDL, DML, destination writes, or resource mutations.
- **Never emit executable mutations:** Write recommendations as prose with
  official documentation links. Do not put runnable resource-changing commands
  or DDL in reports.
- **Location integrity:** Keep queries and reservation resources in their exact
  location. Never mix a multi-region and a single region.
- **Admin/workload separation:** Reservation metadata belongs to the
  administration project; workload jobs belong to workload projects; query jobs
  are created and billed in the query project. Record all three.
- **No silent gaps:** Missing required documentation access, IAM, views, fields,
  history, APIs, or fallbacks must appear as `GAP` or `BLOCKED`.
- **No stale pricing:** If current location-specific prices are not verified
  through official documentation, omit dollar savings and mark them
  `NOT VERIFIED`.
- **Privacy:** Never include raw workload query SQL, user emails, job IDs, error
  messages, or Query 4.2 table identifiers in reports. Explicit approval permits
  ephemeral diagnosis only, not persistence.
- **Fingerprint integrity:** Generate a new ephemeral salt for each run and use
  it for principal, job, and workload-derived table fingerprints. Never print or
  persist the salt. Label Google-provided normalized query hashes separately.
  Approved project/reservation/assignment identifiers and storage-inventory or
  dataset-audit resource names may remain visible when needed for configuration
  scope or an actionable metadata recommendation. Fingerprint generic
  recommendation targets and Write API dataset/table identifiers; omit
  free-form recommendation descriptions.

Prompt guardrails are behavioral policy. Antigravity permissions are the
enforceable boundary. Following the current [Antigravity permissions
documentation](https://www.antigravity.google/docs/cli-permissions), use
`/permissions` to select `strict` or `request-review`. Configure fine-grained
allow/ask/deny rules in Antigravity settings or permission prompts, with deny
rules for operations that current official documentation classifies as
mutating. Do not rely on a finite command or prefix list in this skill. Because
terminal rules might not inspect the SQL payload supplied to a query, live query
execution also requires a dedicated least-privilege principal limited to the
roles in `resources/IAM.md` and verified to lack BigQuery data/resource mutation
permissions. If either the deny policy or effective IAM cannot be verified,
stop; do not claim an enforced read-only run.

## Source grounding

Before using an `OFFICIAL` claim, the product-rule verifier must retrieve the
supporting first-party page using an available read-only documentation or web
capability. Allowed authorities are
`cloud.google.com`, `docs.cloud.google.com`, and `antigravity.google`.
Repository links and model memory are discovery aids, not verification.

Record each used claim as:

| Claim | Source URL | Retrieved | Scope | PASS/GAP | Note |
|---|---|---|---|---|---|

- `PASS`: the page supports the exact value or qualified behavior for the
  target location, edition, CLI version, and preview status.
- `GAP`: the page is unavailable, ambiguous, mismatched, stale, or does not
  support the target scope.
- A strategy-changing `GAP` forces `REVIEW_REQUIRED`.
- A pricing `GAP` prohibits dollar estimates.
- A `GAP` is never relabelled `OFFICIAL`.

## Evidence labels

- `OBSERVED` — returned by a read-only metadata query
- `DERIVED` — deterministic calculation from observations
- `OFFICIAL` — a claim with a current source-grounding `PASS`
- `HEURISTIC` — cookbook planning rule
- `ASSUMPTION` — price, date, workload, or incomplete evidence
- `RECOMMENDATION` — user-executed action; never executed by this skill

## Subagent orchestration

For every broad audit, define and invoke three runtime read-only subagents:

1. **Product-rule verifier** — documentation retrieval enabled; retrieve
   first-party GCP and Antigravity pages; no write tools or cloud terminal access.
2. **SQL reviewer** — documentation retrieval enabled for current schema
   checks; read-only terminal inspection only; no write tools or cloud mutations.
3. **Report reviewer** — documentation access only when a citation needs
   rechecking; no write tools or cloud terminal access.

Set write tools off for all three and instruct reviewers not to delegate. If
the current runtime exposes a separate delegation control, disable it; do not
claim platform enforcement when it does not. The main agent owns inputs,
reconciles evidence, and writes reports. Define and invoke reviewers as runtime
subagents; use `/agents` to monitor them. Use `/tasks` to monitor active
background shell processes.

Each reviewer returns:

| Lane | PASS/GAP | Evidence reviewed | Findings | Blocking impact |
|---|---|---|---|---|

## Execution workflow

### 1. Preflight

- Confirm `agy` was launched from `bq_finops_cookbook` and `/skills` discovers
  `bq-finops-analyst`.
- Select Gemini 3.5 Flash with `/model`. Do not require an undocumented separate
  thinking-level control.
- Retrieve the official pages needed for this run through any available
  read-only documentation or web capability. `/mcp` is relevant only when the
  user has configured an MCP server; it is not a skill prerequisite.
- Inspect `/permissions` and select `strict` or `request-review`. Verify the
  separate fine-grained settings/permission-prompt rules deny operations that
  current official CLI documentation identifies as mutating.
- Identify the active gcloud CLI account and any configured service-account
  impersonation using the current [gcloud authorization](https://docs.cloud.google.com/sdk/docs/authorizing)
  and [`bq` authentication](https://docs.cloud.google.com/bigquery/docs/authentication)
  references. Do not print access tokens.
- Verify that the effective analysis principal has only the required
  least-privilege roles and no BigQuery data/resource mutation permissions.
  Broader inherited or custom access blocks live execution unless the run is
  moved to a dedicated restricted principal.
- Validate the workload, query, and administration project IDs and location.
- Require both analysis bounds or neither and validate
  `analysis_start_ts < analysis_end_ts`. If omitted, bind
  `TIMESTAMP(DATE_SUB(CURRENT_DATE('UTC'), INTERVAL 30 DAY))` as start and
  `TIMESTAMP(CURRENT_DATE('UTC'))` as end. Use the same inclusive start and exclusive end for all
  comparable workload queries. Require hour-aligned bounds for hourly slot
  metrics; ask for corrected bounds rather than rounding them silently. If a
  requested interval exceeds a source's
  documented retention, mark the affected query `BLOCKED` rather than silently
  shortening it. Also record organization-migration coverage because current
  JOBS/JOBS_TIMELINE documentation says history before a project migration can
  be unavailable. A known migration inside the requested interval, or unknown
  migration coverage that cannot be resolved from approved evidence or user
  confirmation, blocks dependent full-window timeline metrics.
- Generate the per-run fingerprint salt in memory; never record it in terminal
  output, reports, or repository files.
- Before any `JOBS_TIMELINE_BY_PROJECT` query, run the internal read-only
  timeline-overlap probe in `resources/finops_agent.md`. Bind its result as
  `timeline_creation_start_ts`. This is a derived execution parameter, not a
  user input or a numbered analysis. If the probe returns no overlapping jobs,
  bind `analysis_start_ts`. If the probe is inaccessible, mark every dependent
  timeline query `BLOCKED`; do not fall back to the analysis start or a fixed
  lookback.
- Record the documentation retrieval date.
- Classify readiness as `READY`, `READY_WITH_OPTIONAL_GAPS`,
  `BLOCKED_LIVE_EXECUTION`, `INSUFFICIENT_EVIDENCE`, or `REVIEW_REQUIRED`.
  Authentication, IAM, permission, project, or location uncertainty blocks
  live execution; strategy-changing scope, documentation, recommender, or
  economic gaps require review.

### 2. Read-only query execution

Construct the current invocation from the official [`bq` CLI
reference](https://docs.cloud.google.com/bigquery/docs/reference/bq-cli-reference)
and [query guide](https://docs.cloud.google.com/bigquery/docs/running-queries).
The resulting query job must explicitly bind the query/billing project, exact
BigQuery location, and GoogleSQL mode, must not configure a destination or other
write behavior, and must pass the corpus SQL without unsafe shell interpolation.

The SQL may contain `SELECT`, CTEs, and local `DECLARE` statements used only by
read-only `SELECT` logic. Use typed named GoogleSQL parameters
`@analysis_start_ts`, `@analysis_end_ts`, `@timeline_creation_start_ts`, and
`@run_fingerprint_salt`. Construct
their current CLI binding syntax from the official `bq` reference; never insert
the salt into query text or a logged shell command, and disable shell tracing
for the invocation. It must not contain DDL or DML.

### 3. Analysis

- Run required configuration queries `0.1`, `0.2`, `0.2a`, and `0.5` first.
  Zero commitment rows from a valid Query 0.2a execution is `PASS`. Then
  evaluate optional `0.3` and `0.4` using their manifest triggers and
  prerequisites.
  Always produce `00_current_configuration.md`.
- Run `1.1` through `1.3`; compute CV with a zero guard, burst ratio with a
  zero-median guard, active/all-hour distributions, p50, p95, p99, maximum, and
  zero-usage share. Timeline evidence covers all observable timeslices that
  overlap the declared window, including jobs created before its start.
- Run applicable `4.x` queries. Reconcile heuristics with Slot
  Recommender/Estimator only when the relevant APIs, IAM, and supported scenario
  are verified. Query 4.9 percentiles include only successful, non-cached,
  positive-compute jobs with valid duration. Preserve failed positive-compute
  evidence in Queries 0.5 and 4.8 instead of mixing failures into those
  percentiles.
- Run applicable `5.1` and `6.x` queries. Keep logical and physical bytes
  separate; table age alone is never deletion evidence. Query 6.3 is a neutral
  forecast sensitivity, not a recommendation. Do not recommend changing a
  storage billing model until dated prices, observed Billing evidence,
  clone/snapshot semantics, time travel, fail-safe storage, and the user's
  materiality threshold are reconciled.
- For every optional query, apply this precedence: absent trigger => `NOT
  APPLICABLE`; present trigger plus any missing execution prerequisite =>
  `BLOCKED`; successful execution with zero rows => `PASS`.

### 4. Decision guardrail

Apply these scenarios before finalizing:

- Incomplete or invalid required metrics => `INSUFFICIENT_EVIDENCE`.
- Zero median => burst ratio `UNDEFINED`; never divide by zero.
- Negligible absolute use or spend => burstiness alone never justifies a
  reservation.
- Standard limit exceeded => never recommend invalid Standard capacity.
- Recommender disagreement => `REVIEW_REQUIRED` with both positions shown.
- `p25 >= 50` alone => insufficient evidence for a commitment.
- Hybrid => `INELIGIBLE`. This version analyzes one workload project and never
  combines parallel runs into a cross-project decision.
- Missing verified billed bytes, dated regional pricing, or actual capacity
  Billing/Slot Recommender evidence => economic comparison `REVIEW_REQUIRED`;
  never claim dollar superiority.

### 5. Reports

Write the seven manifest reports. Every report includes a `Documentation Checks`
section using the source-grounding table. The final report contains, in order:

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

`Documentation Checks` must contain the claim table. `bq / gcloud Execution
Notes` records the active/impersonated gcloud principal, official CLI references
consulted, resolved read-only invocation shape, permission posture, fallbacks,
failures, and confirmation that no cloud
resource changed.

## Completion gate

Do not declare the analysis complete unless:

- every manifest query is `PASS`, `FALLBACK`, `BLOCKED`, or
  `NOT APPLICABLE`;
- every used volatile claim is `PASS` or an explicit `GAP` with its blocking
  impact propagated;
- product-rule, SQL, and report reviewers returned and were reconciled;
- reports agree on metrics, assumptions, and evidence labels;
- pricing is verified or dollar savings are omitted;
- no invalid edition configuration is recommended;
- only read-only `bq`/`gcloud` operations were issued and no resource changed.
