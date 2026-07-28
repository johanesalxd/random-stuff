# Evaluating CA Data Agents with Prism

Phase 10 evaluates the BigQuery Conversational Analytics (CA / GDA) data agents in
this repository with Prism, the open-source CA evaluation application, instead of a
bespoke in-repo harness. This document covers what Prism measures, how to stand it
up, how to configure it against this project, the IAM it needs, and an example test
suite over the demo dataset.

For where this sits in the roadmap, see the Phase 10 section of
[`adk_semantic_layer_plan.md`](./adk_semantic_layer_plan.md).

## What Prism is

Prism (`ca-agent-ops-prism` in `looker-open-source/ca-demos-and-tools`) is a
deployed Dash / Flask application with a PostgreSQL backend. Test suites and their
assertions are authored in the Prism UI and stored in its database; there is no
committable YAML test spec in this repository. Prism runs each case against a live
CA / GDA data agent and records the result, a trace, and per-assertion scores.

Assertion types:

- **Data Check Row** and **Data Check Row Count** -- execute the agent's query for
  real and compare the returned rows (or row count) to expected values. This is the
  execution-accuracy signal.
- **Query Check** -- assertions about the generated SQL.
- **Latency** -- wall-clock bound per case.
- **AI Judge** -- model-graded qualitative assessment of the answer.

Views:

- **Trace View** -- per-run inspection of the agent's steps and generated SQL.
- **A/B Delta dashboard** -- compares two agents or two runs side by side.

## Scope boundary

Prism evaluates **CA / GDA data agents only**. In this repository that means:

- the CA baseline agents (`orders`, `inventory`), and
- the combined `semantic_ca` fallback data agent shipped in Phase 11 (orders plus
  inventory tables), created by `scripts/admin_tools.py`.

Prism does **not** execute the custom `semantic_analytics` ADK Workflow. The
semantic-first guarded path (arms 2 and 3) and grounded-CA delegation (arm 4) are
compared against Prism's CA scores qualitatively; if a driven, execution-accuracy
comparison of the custom path is later required, add a separate custom-workflow
runner as noted in the Phase 10 plan. See the four-arm framing in
[`adk_semantic_layer_plan.md`](./adk_semantic_layer_plan.md).

## Standing up Prism

Prism is deployed, not `pip install`ed. Two supported targets:

- **Local (Docker Compose):** runs the Dash app, a Gunicorn worker, and a local
  PostgreSQL container. Alembic applies the schema migrations on start. Use this for
  interactive evaluation runs.
- **Cloud Run plus Cloud SQL:** the app on Cloud Run with a managed PostgreSQL
  instance for a shared, persistent evaluation history.

Follow the upstream `ca-agent-ops-prism` README for the exact compose file, image
build, and migration commands. This repository does not vendor Prism; it targets
the CA data agents Prism connects to.

## Configuration

Point Prism at this project's CA data agents and a Gen AI client project:

| Variable | Purpose |
|---|---|
| `PRISM_GDA_PROJECTS` | Comma-separated project IDs whose CA / GDA data agents Prism can list and evaluate. Include the project that owns the `orders`, `inventory`, and `semantic_ca` agents. |
| `PRISM_GENAI_CLIENT_PROJECT` | Project used for the Gen AI client (model calls / AI Judge). |
| `PRISM_GENAI_CLIENT_LOCATION` | Region for the Gen AI client. Use a valid Vertex region (for example `us-central1`), not `global`. |

Database connection variables (PostgreSQL host, name, user, password) are set per
the upstream deployment target (Compose env or Cloud SQL connection).

## IAM

The identity Prism runs as needs, at minimum:

- **CA / GDA:** Data Agent Owner or Data Agent Creator on the `PRISM_GDA_PROJECTS`
  agents (create / read / evaluate data agents).
- **BigQuery:** `roles/bigquery.user` (run jobs) plus `roles/bigquery.dataViewer`
  on the evaluated data. Data Check assertions execute real queries, so the
  evaluation identity must be able to read the rows being asserted.
- **Vertex AI:** `roles/aiplatform.user` for the Gen AI client and AI Judge.

Because Data Check assertions read real data, scope this identity to the demo
dataset (`bigquery-public-data.thelook_ecommerce` and any project-local copies)
rather than granting broad data access.

## Example test suite (thelook)

Author a suite in the Prism UI over `bigquery-public-data.thelook_ecommerce`,
targeting the `semantic_ca` agent (and the same cases against `orders` /
`inventory` for the A/B Delta view). Suggested cases:

| Case | Question | Assertion type | Expectation |
|---|---|---|---|
| Simple aggregate | How many orders were completed? | Data Check Row Count | Matches gold count |
| Filtered aggregate | Total revenue for completed orders in 2023 | Data Check Row | Matches gold single-row value |
| Multi-table join | Revenue by product category | Data Check Row | Matches gold category rows |
| Ratio | Return rate by distribution center | Data Check Row | Matches gold per-center ratios |
| Top-N | Top 5 products by units sold | Data Check Row | Matches gold ordered rows |
| Latency guard | (reuse simple aggregate) | Latency | Under the agreed bound |
| Ambiguous | Show me the best performers | AI Judge | Reasonable clarification or defensible interpretation |

Run the suite against each agent, then use the A/B Delta dashboard to compare the
combined `semantic_ca` agent to the single-domain baselines, and read the CA scores
alongside the custom workflow's own provenance for the qualitative arm 2 / arm 3
comparison.
