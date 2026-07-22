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
   - `ADK_LOCAL_APP_NAME`, optional, defaults to `semantic_analytics`
   - `SEMANTIC_CONTRACT_PATH`, optional semantic YAML file or directory

   Agent Engine mode also needs:

   - `GOOGLE_CLOUD_PROJECT`
   - `ORDERS_REASONING_ENGINE_ID`

## Local ADK Mode

Start the ADK API server from the project root:

```bash
export SEMANTIC_CONTRACT_PATH=config/semantic_contracts
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
export ADK_LOCAL_APP_NAME=semantic_analytics
```

Then run the Flask app from `advanced/test_web`.

Local mode creates an ADK API server session at
`/apps/{app_name}/users/{user_id}/sessions`, stores the OAuth token in session
state at `AUTH_RESOURCE_ORDERS`, and calls `/run`.

The current `semantic_analytics` workflow selects semantic context, grounds it
against the catalog (`semantic_narrow` or `catalog_broad`), and generates guarded,
read-only SQL. It dry-runs every query and executes only when
`SQL_EXECUTION_MODE=developer` (plan mode, dry-run only, is the default).

Whose credentials run the query is governed separately by `SQL_AUTH_MODE`. The
default `adc` uses Application Default Credentials. Setting `SQL_AUTH_MODE=user`
binds each query to a per-request OAuth access token read from session state at
`ADK_OAUTH_TOKEN_STATE_KEY` (default `AUTH_RESOURCE_SEMANTIC_ANALYTICS`), and fails
closed to a refusal when the token is absent. Wiring this harness to populate that
key (it currently stores the token at `AUTH_RESOURCE_ORDERS`) is Phase 9 Slice 2.

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
