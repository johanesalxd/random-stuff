# Advanced: Custom ADK Runtime & Semantic Layer

This directory contains the custom ADK (Agent Development Kit) runtime providing the **Layer 3 High-Precision Runtime** of the architecture.

See [`docs/architecture.md`](../docs/architecture.md) for the end-to-end architectural comparison with Out-of-the-Box BigQuery Conversational Analytics (BQCA) and the 3-Layer adoption path.

Use this runtime when you need:

- **Zero-Tolerance KPI Determinism:** Tier-1 deterministic compiler fast-path (`semantic/compiler.py`) for exact metric queries without Stage-2 LLM drift.
- **Cross-Table Ratios:** Native support for ratios spanning multiple tables with unmatched denominator rows (`active_buyer_rate`) using join cardinality guards.
- **Wide Schema Routing:** Modular domain routing across wide schemas (50+ tables) using portable YAML semantic contracts (`config/semantic_contracts/`) and Knowledge Catalog discovery.
- **Pre-Execution Runtime Guardrails:** Dry-run BigQuery policy gates enforcing `SELECT`-only execution, source-table allowlists, and per-query scan byte caps (`SQL_MAX_BYTES_BILLED`).
- **Verifiable 3-Tier Stream Trust:** Machine-readable confidence classification and client-side prose-to-row numeric reconciliation.
- **End-User OAuth Identity Passthrough:** Per-request OAuth tokens forwarded over transport credentials to enforce BigQuery Row-Level Security (RLS) and Column-Level Security (CLS).

For standard native CA API integration (no custom agent runtime required), see the [root README](../README.md).

---

## Directory Structure

```text
advanced/
├── app/
│   └── semantic_analytics/  # High-precision analytics ADK Workflow
│       ├── __init__.py
│       ├── agent.py         # Workflow definition and tool nodes
│       └── evals/           # Native ADK evaluation suite
├── scripts/
│   ├── deploy_agents.sh     # Deploy or stage Semantic Analytics Agent for Agent Engine
│   ├── setup_auth.py        # Create OAuth authorization resource in Gemini Enterprise
│   └── register_agents.py   # Register Agent Engine agent with Gemini Enterprise
├── test_web/
│   ├── app.py               # Flask OAuth test harness with provenance display
│   ├── templates/           # HTML templates
│   └── static/              # CSS stylesheet
├── docs/
│   └── examples/
│       └── chart_with_ca_api.py  # Reference: direct CA API with chart support
└── README.md
```

---

## Prerequisites

Install the advanced runtime dependencies:

```bash
uv sync --extra advanced
```

This adds `google-adk`, Anthropic (`anthropic[vertex]`), BigQuery, and Knowledge Catalog client dependencies.

---

## Local Development & Execution

Test the semantic analytics workflow locally using the ADK CLI:

```bash
# Load environment
set -a; source .env; set +a

# Run the semantic analytics workflow interactively
uv run --extra advanced adk run advanced/app/semantic_analytics
```

The workflow operates in stages:
1. **Semantic Selection:** `gemini-3.5-flash` maps the question to bounded concepts from `config/semantic_contracts/`.
2. **Tier-1 Compiler Fast-Path:** If the question maps cleanly to an exact metric and dimensions, `semantic/compiler.py` generates the exact SQL deterministically.
3. **Tier-2 Guarded Authoring:** For exploratory queries, the query is grounded against narrow YAML context or broad Knowledge Catalog search, passed to `claude-sonnet-4-5`, and validated via pre-execution dry run before executing once against BigQuery.
4. **Result Summarization:** `gemini-3.5-flash` summarizes the result rows, and `semantic/numeric_reconcile.py` verifies all numbers in prose.

### Running Evaluations

To run the native ADK evaluation suite:

```bash
uv run --extra advanced --extra evaluation adk eval \
  advanced/app/semantic_analytics \
  advanced/app/semantic_analytics/evals/thelook_narrow.evalset.json \
  --config_file_path advanced/app/semantic_analytics/evals/eval_config.json \
  --print_detailed_results
```

See [`app/semantic_analytics/evals/README.md`](app/semantic_analytics/evals/README.md) for full evaluation documentation.

---

## Deployment to Vertex AI Agent Engine

### Step 1: Stage or Deploy the Agent Bundle

To preview or stage the deployment bundle without calling cloud APIs:

```bash
bash advanced/scripts/deploy_agents.sh --stage-only /path/to/stage_dir
```

To deploy directly to Vertex AI Agent Engine:

```bash
bash advanced/scripts/deploy_agents.sh
```

Deploys to `us-central1` by default (set `AGENT_ENGINE_LOCATION` in `.env` to target another region). Note the deployed Reasoning Engine resource ID from the output (e.g. `projects/.../locations/.../reasoningEngines/...`).

### Step 2: Create OAuth Authorization Resource

Create the authorization resource in Gemini Enterprise so end-user OAuth tokens are passed through:

```bash
uv run python advanced/scripts/setup_auth.py --auth-id bq-caapi-oauth-semantic
```

### Step 3: Register with Gemini Enterprise

Register the deployed Reasoning Engine agent with Gemini Enterprise:

```bash
uv run python advanced/scripts/register_agents.py \
  --reasoning-engine <REASONING_ENGINE_ID> \
  --auth-id bq-caapi-oauth-semantic
```

---

## Local Web Test Harness

A lightweight Flask web application is provided in `test_web/` to test OAuth passthrough, token refresh, and stream provenance inspection:

```bash
uv run --extra web python advanced/test_web/app.py
```

See [`test_web/README.md`](test_web/README.md) for full configuration and usage instructions.
