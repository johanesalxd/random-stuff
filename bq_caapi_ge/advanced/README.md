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

### Choosing Your Deployment Security Mode

The runtime supports two enterprise execution modes controlled by `DEPLOY_SQL_AUTH_MODE`:

1. **Option A: User OAuth (`DEPLOY_SQL_AUTH_MODE=user`, Default):**
   - Used for Gemini Enterprise, Google Workspace, and the `test_web/app.py` OAuth test harness.
   - End-user Google OAuth bearer tokens are forwarded per request into ADK session state (`ADK_OAUTH_TOKEN_STATE_KEY`).
   - BigQuery evaluates standard Row-Level Security (`FILTER USING`) under the end-user's identity (`SESSION_USER()`).

2. **Option B: Signed Role-SA Impersonation (`DEPLOY_SQL_AUTH_MODE=impersonated_sa`):**
   - Used for custom front-end gateways (Slack, Microsoft Teams, Okta, custom enterprise portals) where end users do not have Google Workspace OAuth tokens.
   - **Zero-Secret Trust Chain:** The client gateway service account (`SQL_ROLE_TRUSTED_CALLER_SA`) signs a short-lived RS256 JWT assertion containing the user identifier and role slug (e.g. `apac_analyst`).
   - **Signature Verification:** Agent Engine verifies the signature against Google's public x509 certificate endpoint (`https://www.googleapis.com/service_accounts/v1/metadata/x509/<caller_sa>`), extracting the `bqca_role` claim without storing any shared secrets in the agent.
   - **Strict Role-SA Impersonation:** Agent Engine impersonates strictly the mapped Role Service Account (`SQL_ROLE_SA_MAP_JSON`), using `roles/iam.serviceAccountTokenCreator` granted on each specific Role SA (never project-wide).

#### How a Custom Gateway Signs an Assertion & Calls Agent Engine

In production, the trusted gateway service account signs an RS256 JWT using Google Cloud IAM Credentials API.

*(Note: `google-cloud-iam` is a client library dependency of your **external gateway service**—e.g. `pip install google-cloud-iam` or `uv add google-cloud-iam` in your gateway repository—not the deployed Agent Engine runtime bundle).*

```python
import json
import time
from google.cloud import iam_credentials_v1

client = iam_credentials_v1.IAMCredentialsClient()
caller_sa_email = "gateway-runner@my-project.iam.gserviceaccount.com"

# 1. Construct role assertion payload (expires in 5 minutes; max allowed TTL is 900s)
now = int(time.time())
payload = json.dumps({
    "iss": caller_sa_email,
    "aud": "bq-caapi-rls",            # Must match SQL_ROLE_ASSERTION_AUDIENCE
    "sub": "user_12345",              # End-user identifier from enterprise IdP
    "bqca_role": "apac_analyst",      # Target role slug mapped in SQL_ROLE_SA_MAP_JSON
    "iat": now,
    "exp": now + 300,
})

# 2. Sign JWT via Google Cloud IAM Credentials API (RS256)
response = client.sign_jwt(
    name=f"projects/-/serviceAccounts/{caller_sa_email}",
    payload=payload,
)
signed_jwt = response.signed_jwt
```

##### Session Creation, Query Streaming & Assertion Lifetime Lifecycle

Because the agent's SQL execution runtime re-verifies `exp` and `iat` on every query turn (enforcing `0 < (exp - iat) <= 900s` and `exp > current_time`), passing an expired assertion into an existing session will cause subsequent turns to fail closed with an authentication error.

Custom gateways should create a new session whenever a fresh short-lived assertion is minted (the same pattern used by `test_web/app.py` whenever an OAuth token refreshes):
1. **Create a Session With the Signed Role Assertion:**
   ```http
   POST https://us-central1-aiplatform.googleapis.com/v1/projects/{project}/locations/us-central1/reasoningEngines/{engine_id}/sessions
   Content-Type: application/json
   Authorization: Bearer <GATEWAY_SA_OAUTH_TOKEN>

   {
     "userId": "user_12345",
     "sessionState": {
       "bq-caapi-role-assertion": "<SIGNED_JWT>"
     }
   }
   ```
   Parse the `session_id` from the returned resource `name` (`resp.json()["name"].split("/sessions/")[1].split("/")[0]`). Note that `userId` (`"user_12345"`) must match the assertion's `sub` claim—the runtime binds `ctx.session.user_id` to `sub` to reject cross-user assertion replay.

2. **Stream Queries Against the Reasoning Engine Endpoint:**
   ```http
   POST https://us-central1-aiplatform.googleapis.com/v1/projects/{project}/locations/us-central1/reasoningEngines/{engine_id}:streamQuery
   Content-Type: application/json
   Authorization: Bearer <GATEWAY_SA_OAUTH_TOKEN>

   {
     "input": {
       "message": "What is our active buyer rate in APAC?",
       "user_id": "user_12345",
       "session_id": "{session_id}"
     }
   }
   ```
   When the assertion approaches expiry (e.g. after 4 minutes of a 5-minute TTL), mint a fresh assertion and create a new session with the updated `sessionState`.

> **Security Note — Session State Visibility & Replay Window:** Anyone possessing `aiplatform.sessions.get` on the Reasoning Engine instance can inspect `sessionState`, and a captured assertion remains valid for `sub` until its `exp` timestamp (bounded by `SQL_ROLE_ASSERTION_MAX_TTL_SECONDS`). Keep assertion TTLs short (`300s`) and restrict Vertex AI Reasoning Engine IAM permissions strictly to the trusted gateway service account (`roles/aiplatform.user`) and administrative principals.

For local testing with `adk run` without cloud IAM credentials, the gateway can mint an HMAC assertion using a local secret:

```python
from semantic.rls_impersonation import mint_hmac_role_assertion

# Local development / test only:
token = mint_hmac_role_assertion(
    role="apac_analyst",
    subject="local_dev_user",
    hmac_secret="local-test-secret-at-least-32-chars-long",
    ttl_seconds=300,
)
```

---

### Step 1: Stage or Deploy the Agent Bundle

To preview or stage the deployment bundle without calling cloud APIs:

```bash
bash advanced/scripts/deploy_agents.sh --stage-only /path/to/stage_dir
```

To deploy directly to Vertex AI Agent Engine with user OAuth:

```bash
DEPLOY_SQL_AUTH_MODE=user bash advanced/scripts/deploy_agents.sh
```

Or deploy with signed Role-SA impersonation for custom gateways:

```bash
DEPLOY_SQL_AUTH_MODE=impersonated_sa \
SQL_ROLE_TRUSTED_CALLER_SA=gateway-runner@my-project.iam.gserviceaccount.com \
SQL_ROLE_SA_MAP_JSON='{"apac_analyst": "role-apac@my-project.iam.gserviceaccount.com"}' \
bash advanced/scripts/deploy_agents.sh
```

Deploys to `us-central1` by default (set `AGENT_ENGINE_LOCATION` in `.env` to target another region). Note the deployed Reasoning Engine resource ID from the output (e.g. `projects/.../locations/.../reasoningEngines/...`).

### Step 2: Create OAuth Authorization Resource (User Mode Only)

For `DEPLOY_SQL_AUTH_MODE=user`, create the authorization resource in Gemini Enterprise so end-user OAuth tokens are passed through:

```bash
uv run python advanced/scripts/setup_auth.py --auth-id bq-caapi-oauth-semantic
```

### Step 3: Register with Gemini Enterprise (User Mode Only)

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
