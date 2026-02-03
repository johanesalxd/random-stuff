# A2A Bridge Debugging & Handoff (Feb 04, 2026)

## Current Architecture
- **Bridge:** FastAPI app deployed to Google Cloud Run.
- **Service URL:** `https://bq-caapi-bridge-7uhrhkaiiq-uc.a.run.app`
- **Backend:** Google Conversational Analytics (CA) API.
- **Identity:** OAuth Identity Passthrough. User tokens are extracted from `Authorization: Bearer <token>` and passed to the CA API.
- **Agent IDs:**
  - Order & User Analyst: `agent_e44f2e7a-4620-4653-a3f7-d7c24f3d0e14`
  - Inventory & Product Analyst: `inventory_product_agent`

## The Blocker Issue
Gemini Enterprise reports an `INTERNAL` error (500) with a `REMOTE_AGENT_FAILURE`.
The underlying cause is a **Pydantic Validation Error** on the A2A response returned by the Bridge.

### Error Payload Analysis
```json
{
  "message": "Agent failed with error: A2A request failed: 6 validation errors for SendMessageResponse... SendMessageSuccessResponse.result.Message.role\n  Input should be 'agent' or 'user' [type=enum, input_value='model', input_type=str]"
}
```

### The Findings
1.  **Role Enum:** The A2A validator strictly allows `agent` or `user`. Our code was sending `model`.
2.  **Schema Matching:** Because the `role` validation failed for the `Message` schema, the validator attempted to check if the response was a `Task`. This caused several confusing "Task field required" errors.
3.  **JSON-RPC:** The bridge correctly handles JSON-RPC 2.0 requests from Gemini Enterprise (`method: message/send`).

## The Solution
The fix requires a single-line change in `app/bridge.py` inside the `orders_chat` and `inventory_chat` handlers.

### Code Fix
```python
# app/bridge.py

# CHANGE THIS:
"role": "model",

# TO THIS:
"role": "agent",
```

### Response Structure (Target)
```json
{
  "jsonrpc": "2.0",
  "id": "<request_id>",
  "result": {
    "messageId": "<uuid>",
    "createTime": "YYYY-MM-DDTHH:MM:SSZ",
    "kind": "message",
    "role": "agent",
    "parts": [{"kind": "text", "text": "..."}]
  }
}
```

## How to Resume & Verify

### 1. Apply Fix
Edit `app/bridge.py` and replace `role: "model"` with `role: "agent"`.

### 2. Redeploy
```bash
gcloud run deploy bq-caapi-bridge \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars GOOGLE_CLOUD_PROJECT=johanesa-playground-326616,GOOGLE_CLOUD_LOCATION=global,AGENT_ORDERS_ID=agent_e44f2e7a-4620-4653-a3f7-d7c24f3d0e14,AGENT_INVENTORY_ID=inventory_product_agent,BIGQUERY_DATASET_ID=thelook_ecommerce \
  --quiet
```

### 3. Check Logs
If it fails, monitor the Cloud Run logs immediately:
```bash
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=bq-caapi-bridge" --limit 10
```

## Reference Documents
- [A2A Protocol Specification](https://a2a-protocol.org/)
- [Gemini Enterprise A2A Registration](https://docs.cloud.google.com/gemini/enterprise/docs/register-and-manage-an-a2a-agent)
- [A2A Quickstart Notebook](https://github.com/a2aproject/a2a-samples/blob/main/notebooks/a2a_quickstart.ipynb)
- [A2A Python Samples](https://github.com/a2aproject/a2a-samples/tree/main/samples/python)
