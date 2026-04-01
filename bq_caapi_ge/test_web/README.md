# Test Web App

Simple Flask app to test OAuth passthrough to Agent Engine.

## Setup

```bash
cd test_web
pip install -r requirements.txt
```

## Prerequisites

1. OAuth redirect URI configured in Google Cloud Console:
   - Add `http://localhost:8080/auth/callback` to your OAuth client

2. Agent deployed to Agent Engine

3. Environment variables in `../.env`:
   - `OAUTH_CLIENT_ID`
   - `OAUTH_CLIENT_SECRET`
   - `GOOGLE_CLOUD_PROJECT`
   - `ORDERS_REASONING_ENGINE_ID`
   - `AUTH_RESOURCE_ORDERS`

## Run

```bash
python app.py
```

Open http://localhost:8080 in your browser.

## How It Works

1. Login with Google OAuth
2. App captures your access token
3. When you send a query:
   - Creates Agent Engine session with token in `sessionState[AUTH_RESOURCE_ORDERS]`
   - Calls `:streamQuery`
   - `DataAgentCredentialsConfig(external_access_token_key=...)` reads the token
     directly from session state on each tool call
   - DataAgentToolset uses your token for BigQuery queries
4. Results displayed in chat
