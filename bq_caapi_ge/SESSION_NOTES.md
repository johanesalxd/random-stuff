# Session Notes: BQ Conversational Analytics + Gemini Enterprise

**Last Updated:** 2026-02-05

## Project Overview

ADK Agents deployed to Vertex AI Agent Engine that wrap the Conversational Analytics API (Data Agents) with OAuth identity passthrough.

**Project:** `johanesa-playground-326616`
**Location:** `/Users/johanesa/Developer/git/random-stuff/bq_caapi_ge`

## Current State

### Deployed Resources

| Resource | ID | Description |
|----------|-----|-------------|
| Orders Agent | `4844258016469450752` | Queries orders, users, events data |
| OAuth Auth Resource | `bq-caapi-oauth` | OAuth authorization for orders agent |

### OAuth Token Bridge

The key challenge was bridging OAuth tokens from Gemini Enterprise to DataAgentToolset:

- **Gemini Enterprise stores tokens at:** `session_state[auth_resource_id]` (e.g., `bq-caapi-oauth`)
- **DataAgentToolset expects tokens at:** `session_state["data_agent_token_cache"]`

**Solution:** `before_tool_callback` bridges the token with proper format:

```python
async def bridge_oauth_token(tool, args, tool_context):
    access_token = tool_context.state.get(AUTH_RESOURCE_ID)
    
    if access_token and not tool_context.state.get(TOKEN_CACHE_KEY):
        expiry_time = (datetime.utcnow() + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        token_data = {
            "token": access_token,
            "refresh_token": "",  # Empty - Gemini Enterprise only provides access_token
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": OAUTH_CLIENT_ID,
            "client_secret": OAUTH_CLIENT_SECRET,
            "scopes": SCOPES,
            "expiry": expiry_time,
        }
        tool_context.state[TOKEN_CACHE_KEY] = json.dumps(token_data)
    
    return None
```

**Key insight:** The `expiry` field must be set to a future time for `creds.valid = True`.

## Test Web App

A Flask app at `test_web/` simulates Gemini Enterprise OAuth passthrough:

```bash
cd test_web
uv venv .venv
source .venv/bin/activate
uv pip install --index-url https://pypi.org/simple/ -r requirements.txt
python app.py
# Open http://localhost:8080
```

**Flow:**
1. User logs in via Google OAuth
2. Access token captured in session
3. Query creates Agent Engine session with token in `sessionState`
4. Agent's bridge callback copies token to DataAgentToolset format
5. BigQuery query runs with user's identity

## Configuration

### Root `.env`

```bash
GOOGLE_CLOUD_PROJECT=johanesa-playground-326616
GOOGLE_CLOUD_PROJECT_NUMBER=605626490127
OAUTH_CLIENT_ID=<client-id>
OAUTH_CLIENT_SECRET=<client-secret>
AUTH_RESOURCE_ORDERS=bq-caapi-oauth
AUTH_RESOURCE_INVENTORY=bq-caapi-oauth-inventory
ORDERS_REASONING_ENGINE_ID=4844258016469450752
```

### Per-Agent `.env`

Each agent directory (`app/orders/`, `app/inventory/`) needs:

```bash
GOOGLE_CLOUD_PROJECT=johanesa-playground-326616
AGENT_ORDERS_ID=<data-agent-id>
OAUTH_CLIENT_ID=<client-id>
OAUTH_CLIENT_SECRET=<client-secret>
```

## Useful Commands

### Deploy Agent

```bash
uv run adk deploy agent_engine app/orders \
  --project=johanesa-playground-326616 \
  --region=us-central1 \
  --display_name="Orders Analyst"
```

### Test Agent via API

```bash
# Create session with token
curl -X POST -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  "https://us-central1-aiplatform.googleapis.com/v1/projects/johanesa-playground-326616/locations/us-central1/reasoningEngines/4844258016469450752/sessions" \
  -d '{"userId": "test-user", "sessionState": {"bq-caapi-oauth": "USER_ACCESS_TOKEN"}}'

# Query
curl -X POST -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  "https://us-central1-aiplatform.googleapis.com/v1/projects/johanesa-playground-326616/locations/us-central1/reasoningEngines/4844258016469450752:streamQuery" \
  -d '{"input": {"message": "How many orders?", "user_id": "test", "session_id": "SESSION_ID"}}'
```

### Check Logs

```bash
gcloud logging read "resource.type=\"aiplatform.googleapis.com/ReasoningEngine\" AND resource.labels.reasoning_engine_id=\"4844258016469450752\"" \
  --project=johanesa-playground-326616 --limit=30
```

## Project Structure

```
bq_caapi_ge/
├── app/
│   ├── orders/agent.py       # Orders agent with OAuth bridge
│   ├── inventory/agent.py    # Inventory agent with OAuth bridge
│   └── __init__.py
├── scripts/
│   ├── deploy_agents.sh      # Deployment script
│   ├── setup_auth.py         # Create OAuth auth resources
│   └── register_agents.py    # Register with Gemini Enterprise
├── test_web/                 # OAuth test harness
│   ├── app.py
│   ├── templates/
│   └── static/
├── .env                      # Environment variables
└── SESSION_NOTES.md          # This file
```

## Key Learnings

1. **Token format matters:** DataAgentToolset uses `from_authorized_user_info()` which requires `refresh_token` key to exist (can be empty) and `expiry` in the future for `valid=True`.

2. **Bridge callback pattern:** Use `before_tool_callback` to copy tokens between state keys before tool execution.

3. **OAuth scope relaxation:** Google may add scopes during OAuth flow. Set `OAUTHLIB_RELAX_TOKEN_SCOPE=1` to accept this.

4. **Per-agent .env:** ADK reads `.env` from the agent directory during deployment, not the project root.
