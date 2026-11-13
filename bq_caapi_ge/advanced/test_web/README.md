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
   - Agent Engine mode: set `SEMANTIC_REASONING_ENGINE_ID`

3. Environment variables in root `../../.env`:
    - `OAUTH_CLIENT_ID`
    - `OAUTH_CLIENT_SECRET`
    - `FLASK_SECRET_KEY`, recommended; a stable secret keeps signed session cookies
      valid across restarts. An ephemeral secret is generated (with a warning) when
      unset.
    - `COOKIE_SECURE`, optional; set to `1` to mark session cookies `Secure` when
      serving over HTTPS.
    - `ADK_OAUTH_TOKEN_STATE_KEY`, optional; the session-state key the user token is
      written to. Defaults to `AUTH_RESOURCE_SEMANTIC_ANALYTICS` if set, otherwise
      `"bq-caapi-oauth-semantic"`, and must match the target agent's `external_access_token_key`.

   Local ADK API server mode also needs:

   - `ADK_LOCAL_BASE_URL`, for example `http://127.0.0.1:8000`
   - `ADK_LOCAL_APP_NAME`, optional, defaults to `semantic_analytics`
   - `SEMANTIC_CONTRACT_PATH`, optional semantic YAML file or directory

   Agent Engine mode also needs:

   - `GOOGLE_CLOUD_PROJECT`
   - `SEMANTIC_REASONING_ENGINE_ID`

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
state at `ADK_OAUTH_TOKEN_STATE_KEY` (defaulting to `AUTH_RESOURCE_SEMANTIC_ANALYTICS` if set, otherwise `"bq-caapi-oauth-semantic"`),
and calls `/run`. The backend session is reused across queries and recreated only
when the token is refreshed.

The current `semantic_analytics` workflow selects semantic context, grounds it
against exact YAML sources or Knowledge Catalog (`semantic_narrow` or
`catalog_broad`), generates SQL once, executes it with writes blocked, and
summarizes the returned rows.

Whose credentials run the query is governed separately by `SQL_AUTH_MODE`:
- **`SQL_AUTH_MODE=adc`**: Uses local Application Default Credentials (shared developer identity for local testing and benchmark runs).
- **`SQL_AUTH_MODE=user`**: Binds each query to the per-request OAuth access token this harness writes to `ADK_OAUTH_TOKEN_STATE_KEY`, and fails closed with a query error when the token is absent. This matches production `DEPLOY_SQL_AUTH_MODE=user` in Gemini Enterprise and Google Workspace.
- **`SQL_AUTH_MODE=impersonated_sa`**: Used by custom enterprise gateways (Slack, Microsoft Teams, Okta portals) where end users do not have Google Workspace OAuth tokens. Instead of passing an OAuth token, the trusted gateway signs a short-lived RS256 JWT role assertion.
  *(Note: `test_web/app.py` is a Google OAuth development harness for `SQL_AUTH_MODE=user` or `adc`, and does **not** mint role assertions for `SQL_AUTH_MODE=impersonated_sa`. For custom gateway integration and `impersonated_sa` deployment details, see [`../README.md`](../README.md).)*

```python
# Custom enterprise gateway role assertion signing example:
import json, time
from google.cloud import iam_credentials_v1

client = iam_credentials_v1.IAMCredentialsClient()
caller_sa = "gateway-runner@my-project.iam.gserviceaccount.com"
now = int(time.time())
payload = json.dumps({
    "iss": caller_sa,
    "aud": "bq-caapi-rls",
    "sub": "user_12345",
    "bqca_role": "apac_analyst",
    "iat": now,
    "exp": now + 300,
})
response = client.sign_jwt(name=f"projects/-/serviceAccounts/{caller_sa}", payload=payload)
# Passed to agent session state: session_state["bq-caapi-role-assertion"] = response.signed_jwt
```

For local testing with `adk run` without GCP IAM credentials, mint an HMAC assertion:

```python
from semantic.rls_impersonation import mint_hmac_role_assertion

token = mint_hmac_role_assertion(
    role="apac_analyst",
    subject="local_dev_user",
    hmac_secret="local-test-secret-at-least-32-chars-long",
    ttl_seconds=300,
)
```

## Agent Engine Mode

Unset `ADK_LOCAL_BASE_URL` and set `GOOGLE_CLOUD_PROJECT` plus
`SEMANTIC_REASONING_ENGINE_ID`. The app creates an Agent Engine session with the
OAuth token in `sessionState[ADK_OAUTH_TOKEN_STATE_KEY]`, then calls
`:streamQuery`.

## Run

```bash
uv run --extra web python advanced/test_web/app.py
```

Open http://localhost:8080 in your browser.

## How It Works

1. Login with Google OAuth; the callback validates the OAuth `state` before
   exchanging the authorization code. During flow initialization, the transient
   PKCE `code_verifier` is stored temporarily in Flask's signed cookie session
   (`session["oauth_code_verifier"]`) and restored onto the callback Flow instance
   before being popped on successful code exchange.
2. The access token, refresh token, and expiry are held in a server-side store;
   only an opaque session id is placed in the signed cookie. Token credentials
   are never stored in the client-side cookie.
3. When you send a query, the app refreshes the token if it has expired (or asks
   you to reauthenticate), then reuses a backend session with the token in session
   state under `ADK_OAUTH_TOKEN_STATE_KEY`.
4. The selected backend runs the agent.
5. Results and the reasoning-path / execution provenance are returned for display.

## Tests

```bash
uv run --extra advanced --extra web pytest tests/test_web_app.py
```
