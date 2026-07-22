# Test Web App

Simple Flask app to test OAuth passthrough to Agent Engine or a local ADK API
server.

This is a development harness, not a production identity service.

## Setup

The Flask and OAuth dependencies are declared in the `web` extra. Run everything
from the project root:

```bash
uv run --extra web python advanced/test_web/app.py
```

There is no separate virtualenv or manual `uv pip install` step.

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
    - `FLASK_SECRET_KEY`, recommended; a stable secret keeps signed session cookies
      valid across restarts. An ephemeral secret is generated (with a warning) when
      unset.
    - `COOKIE_SECURE`, optional; set to `1` to mark session cookies `Secure` when
      serving over HTTPS.
    - `ADK_OAUTH_TOKEN_STATE_KEY`, optional; the session-state key the user token is
      written to. Defaults to `AUTH_RESOURCE_SEMANTIC_ANALYTICS` and must match the
      engine's value.

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
state at `ADK_OAUTH_TOKEN_STATE_KEY` (default `AUTH_RESOURCE_SEMANTIC_ANALYTICS`),
and calls `/run`. The backend session is reused across queries and recreated only
when the token is refreshed.

The current `semantic_analytics` workflow selects semantic context, grounds it
against the catalog (`semantic_narrow` or `catalog_broad`), and generates guarded,
read-only SQL. It dry-runs every query and executes only when
`SQL_EXECUTION_MODE=developer` (plan mode, dry-run only, is the default).

Whose credentials run the query is governed separately by `SQL_AUTH_MODE`. The
default `adc` uses Application Default Credentials. Setting `SQL_AUTH_MODE=user`
binds each query to the per-request OAuth access token this harness writes to
`ADK_OAUTH_TOKEN_STATE_KEY`, and fails closed to a refusal when the token is
absent.

## Agent Engine Mode

Unset `ADK_LOCAL_BASE_URL` and set `GOOGLE_CLOUD_PROJECT` plus
`ORDERS_REASONING_ENGINE_ID`. The app creates an Agent Engine session with the
OAuth token in `sessionState[ADK_OAUTH_TOKEN_STATE_KEY]`, then calls
`:streamQuery`.

## Run

```bash
uv run --extra web python advanced/test_web/app.py
```

Open http://localhost:8080 in your browser.

## How It Works

1. Login with Google OAuth; the callback validates the OAuth `state` before
   exchanging the authorization code.
2. The access token, refresh token, and expiry are held in a server-side store;
   only an opaque session id is placed in the signed cookie.
3. When you send a query, the app refreshes the token if it has expired (or asks
   you to reauthenticate), then reuses a backend session with the token in session
   state under `ADK_OAUTH_TOKEN_STATE_KEY`.
4. The selected backend runs the agent.
5. Results and the reasoning-path / execution provenance are returned for display.

## Tests

```bash
uv run --extra advanced --extra web pytest tests/test_web_app.py
```
