# Evaluating CA Data Agents with Prism

This guide evaluates the BigQuery Conversational Analytics (CA / GDA) data agents in
this repository with Prism, the open-source CA evaluation application, instead of a
bespoke in-repo harness. This document covers what Prism measures, how to stand it
up, how to configure it against this project, the IAM it needs, and an example test
suite over the demo dataset.

For the current semantic workflow design, see
[`adk_semantic_layer_plan_v2.md`](./adk_semantic_layer_plan_v2.md).

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

Prism evaluates **CA / GDA data agents only**. In this repository that means the
`orders` and `inventory` baseline agents.

Prism does **not** execute the custom `semantic_analytics` ADK Workflow. The
semantic-first workflow is compared against Prism's CA scores qualitatively. If a
driven execution-accuracy comparison of the custom path is required, add a separate
custom-workflow runner.

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
| `PRISM_GDA_PROJECTS` | Comma-separated project IDs whose CA / GDA data agents Prism can list and evaluate. Include the project that owns the `orders` and `inventory` agents. |
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

Author suites in the Prism UI over `bigquery-public-data.thelook_ecommerce`,
targeting `orders` for customer and order cases and `inventory` for product and
logistics cases. Suggested cases:

| Case | Question | Assertion type | Expectation |
|---|---|---|---|
| Simple aggregate | How many orders were completed? | Data Check Row Count | Matches gold count |
| Filtered aggregate | Total revenue for completed orders in 2023 | Data Check Row | Matches gold single-row value |
| Multi-table join | Inventory count by product category | Data Check Row | Matches gold category rows |
| Inventory aggregate | Inventory count by distribution center | Data Check Row | Matches gold per-center rows |
| Top-N | Top 5 products by inventory count | Data Check Row | Matches gold ordered rows |
| Latency guard | (reuse simple aggregate) | Latency | Under the agreed bound |
| Ambiguous | Show me the best performers | AI Judge | Reasonable clarification or defensible interpretation |

Run each suite against its domain agent and read the CA scores alongside the custom
workflow's provenance for a qualitative comparison.
