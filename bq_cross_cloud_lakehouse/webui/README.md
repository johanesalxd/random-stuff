# Froyo Lakehouse Web UI

Flask chat front-end for the Froyo Lakehouse Analyst data agent. Users sign in
with Google OAuth, and the app forwards their access token to the
Conversational Analytics API so every query runs under the signed-in user's own
BigQuery permissions.

This is a demo harness, not a production identity service. Sessions are held in
process memory, so it runs as a single instance.

## How it works

1. `/auth/login` starts the OAuth authorization-code flow.
2. `/auth/callback` validates the OAuth `state` parameter, exchanges the code,
   and stores the access token, refresh token, and expiry server-side. Only an
   opaque session id goes into the signed cookie.
3. `/api/query` refreshes the token when it is within 60s of expiry, then POSTs
   to `geminidataanalytics.googleapis.com/v1beta/...:chat` with the user's
   bearer token and the `dataAgents/<AGENT_ID>` context.
4. The streamed response is parsed into the answer text, the generated SQL, the
   row count, and an optional Vega chart config, all rendered in `chat.html`.

## Configuration

Environment is loaded from `../config.local.env`, then `../agent/.env`, then a
local `.env` in this directory, with later files winning.

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `OAUTH_CLIENT_ID` | yes | — | Google OAuth client id |
| `OAUTH_CLIENT_SECRET` | yes | — | Google OAuth client secret |
| `GCP_PROJECT` / `GOOGLE_CLOUD_PROJECT` | yes | — | Project owning the data agent |
| `AGENT_ID` | no | `froyo_lakehouse_analyst` | CA API data agent id |
| `GOOGLE_CLOUD_LOCATION` | no | `global` | CA API location |
| `OAUTH_REDIRECT_URI` | no | `http://localhost:8080/auth/callback` | Must match an Authorized Redirect URI on the OAuth client |
| `FLASK_SECRET_KEY` | recommended | ephemeral | Stable value keeps sessions valid across restarts |
| `PORT` | no | `8080` | Listen port |
| `COOKIE_SECURE` | no | `0` | Set to `1` when serving over HTTPS |
| `FLASK_DEBUG` | no | `0` | Dev server debugger. Never enable on a reachable service |
| `ALLOW_MOCK_LOGIN` | no | `0` | Skip OAuth entirely. Local UI work only |
| `USE_ADC_FOR_API` | no | `0` | Query as the service identity instead of the user |

### Security notes

- `ALLOW_MOCK_LOGIN=1` lets anyone reaching the app obtain a session without
  credentials. Without it, the app returns `503` from `/auth/login` when OAuth
  credentials are missing rather than issuing a mock token.
- `USE_ADC_FOR_API=1` discards per-user authorization and runs every query as
  the service's own identity. Enabling it together with `ALLOW_MOCK_LOGIN` is
  refused at startup, since that combination lets anonymous callers query
  BigQuery as the service account.
- `FLASK_DEBUG=1` exposes the Werkzeug interactive debugger, which is remote
  code execution on any reachable endpoint. It only affects the `python app.py`
  dev path; container deployments run gunicorn and never read it.

## Run locally

Add `http://localhost:8080/auth/callback` as an Authorized Redirect URI on your
OAuth client, then:

```bash
uv run python app.py
```

Open http://localhost:8080.

To work on the UI without OAuth credentials:

```bash
ALLOW_MOCK_LOGIN=1 uv run python app.py
```

## Deploy

`../deploy_no_aws.sh` builds this directory with Cloud Build and deploys it to
Cloud Run. It stores `OAUTH_CLIENT_ID`, `OAUTH_CLIENT_SECRET`, and
`FLASK_SECRET_KEY` in Secret Manager, grants the runtime service account read
access, and deploys twice: once to learn the service URL, then again with
`OAUTH_REDIRECT_URI` pinned to `<service-url>/auth/callback`.

Register that same callback URL on your OAuth client or sign-in will fail.

The container serves through gunicorn with a single worker, and the service is
pinned to `--max-instances=1` to match the in-process session store. Moving
sessions to a shared store is a prerequisite for scaling out.

## Prerequisites

The data agent must already exist. Deploy it with `../deploy_demo.sh`
(cross-cloud) or `../deploy_no_aws.sh` (GCP-only) before using this UI.

Signed-in users need BigQuery and Conversational Analytics access on the
project, because queries run with their credentials rather than the service's.
