# Test Web App

Simple Flask app to test OAuth passthrough to Agent Engine or a local ADK API
server.

## Setup

```bash
cd advanced/test_web
uv venv .venv
source .venv/bin/activate
uv pip install --index-url https://pypi.org/simple/ flask requests google-auth-oauthlib python-dotenv
```

## Prerequisites

1. OAuth redirect URI configured in Google Cloud Console:
   - Add `http://localhost:8080/auth/callback` to your OAuth client

2. Backend runtime

   Use one of these modes:

   - Local ADK API server mode: set `ADK_LOCAL_BASE_URL`
   - Agent Engine mode: set `ORDERS_REASONING_ENGINE_ID`

3. Environment variables in root `../../.env`:
    - `OAUTH_CLIENT_ID`
    - `OAUTH_CLIENT_SECRET`
    - `AUTH_RESOURCE_ORDERS`

   Local ADK API server mode also needs:

   - `ADK_LOCAL_BASE_URL`, for example `http://127.0.0.1:8000`
   - `ADK_LOCAL_APP_NAME`, optional, defaults to `certified_analytics`
   - `SEMANTIC_EXECUTION_MODE`, optional, defaults to `compile_only`
   - `SEMANTIC_MAX_RESULTS`, optional, defaults to `100`
   - `SEMANTIC_MAXIMUM_BYTES_BILLED`, optional BigQuery cost guardrail
   - `SEMANTIC_GROUNDING_MODE`, optional, defaults to `disabled`
   - `SEMANTIC_GROUNDING_PAGE_SIZE`, optional, defaults to `5`

   Agent Engine mode also needs:

   - `GOOGLE_CLOUD_PROJECT`
   - `ORDERS_REASONING_ENGINE_ID`

## Local ADK Mode

Start the ADK API server from the project root:

```bash
export GOOGLE_CLOUD_PROJECT=your-project-id
export SEMANTIC_EXECUTION_MODE=compile_only
export SEMANTIC_GROUNDING_MODE=disabled
uv run --extra advanced adk api_server advanced/app \
  --port 8000 \
  --auto_create_session \
  --reload_agents
```

Set all `SEMANTIC_*` variables in this API-server terminal before startup. The
Flask app loads the root `.env` for its own process only; changing variables in
the Flask terminal does not reconfigure an already-running ADK server.

In another terminal, configure the test web app:

```bash
export ADK_LOCAL_BASE_URL=http://127.0.0.1:8000
export ADK_LOCAL_APP_NAME=certified_analytics
```

Then run the Flask app from `advanced/test_web`.

Local mode creates an ADK API server session at
`/apps/{app_name}/users/{user_id}/sessions`, stores the OAuth token in session
state at `AUTH_RESOURCE_ORDERS`, and calls `/run`.

The semantic-layer prototype defaults to compile-only mode. It returns
contract-validated SQL and metadata without querying BigQuery. The current
full-match intent selector is not sufficient for end-to-end certification, so the
response remains `certified=false`:

```bash
export SEMANTIC_EXECUTION_MODE=compile_only
export SEMANTIC_GROUNDING_MODE=disabled
```

To add Dataplex-backed catalog retrieval through lower-level ADK BigQuery helpers
without executing SQL, restart the API server with:

```bash
export SEMANTIC_EXECUTION_MODE=compile_only
export SEMANTIC_GROUNDING_MODE=adk_bigquery_adc
export SEMANTIC_GROUNDING_PAGE_SIZE=5
export GOOGLE_CLOUD_PROJECT=your-project-id
gcloud auth application-default login
```

To execute compiled SQL locally through lower-level ADK BigQuery helpers with
ADC, restart the API server with:

```bash
export SEMANTIC_EXECUTION_MODE=adk_bigquery_adc
export SEMANTIC_GROUNDING_MODE=adk_bigquery_adc
export SEMANTIC_MAX_RESULTS=100
export SEMANTIC_MAXIMUM_BYTES_BILLED=10485760
export GOOGLE_CLOUD_PROJECT=your-project-id
gcloud auth application-default login
```

Both ADC execution modes are developer-only and return `certified=false`.
`adc_developer` uses the BigQuery client directly and supports compiler query
parameters. `adk_bigquery_adc` uses lower-level ADK helpers but currently refuses
parameterized queries. Credential-managed `BigQueryToolset` user-token execution
is intentionally deferred to the next checkpoint.

Catalog assets are returned as diagnostic metadata only. They do not influence
the prototype full-match selector yet and must not be described as grounded intent
selection.

## Agent Engine Mode

Unset `ADK_LOCAL_BASE_URL` and set `GOOGLE_CLOUD_PROJECT` plus
`ORDERS_REASONING_ENGINE_ID`. The app creates an Agent Engine session with the
OAuth token in `sessionState[AUTH_RESOURCE_ORDERS]`, then calls `:streamQuery`.

## Run

```bash
python app.py
```

Open http://localhost:8080 in your browser.

## How It Works

1. Login with Google OAuth
2. App captures your access token
3. When you send a query, the app creates a backend session with the token in
   session state
4. The selected backend runs the agent
5. Results are displayed in chat
