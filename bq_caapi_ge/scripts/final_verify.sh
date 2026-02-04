#!/bin/bash

# Configuration
PROJECT_ID="johanesa-playground-326616"
LOCATION="us-central1"
ORDERS_RESOURCE="2600902452085522432"
INVENTORY_RESOURCE="4581360388221698048"

# Auth
TOKEN=$(unset GOOGLE_APPLICATION_CREDENTIALS && gcloud auth print-access-token)

test_agent() {
    local name=$1
    local resource=$2
    echo "--- Testing $name ($resource) ---"

    # 1. Create Session
    echo "1. Creating Session..."
    SESSION_RESP=$(curl -s -X POST \
      -H "Authorization: Bearer $TOKEN" \
      -H "Content-Type: application/json" \
      "https://$LOCATION-aiplatform.googleapis.com/v1/projects/$PROJECT_ID/locations/$LOCATION/reasoningEngines/$resource:query" \
      -d '{"class_method": "async_create_session", "input": {"user_id": "verify_user"}}')

    echo "Session Response: $SESSION_RESP"
    SESSION_ID=$(echo "$SESSION_RESP" | grep -o '"id": "[^"]*' | head -1 | cut -d'"' -f4)

    if [ -n "$SESSION_ID" ]; then
        echo "2. Sending Query (Session: $SESSION_ID)..."
        curl -X POST \
          -H "Authorization: Bearer $TOKEN" \
          -H "Content-Type: application/json" \
          "https://$LOCATION-aiplatform.googleapis.com/v1/projects/$PROJECT_ID/locations/$LOCATION/reasoningEngines/$resource:query?alt=sse" \
          -d "{
            \"class_method\": \"async_stream_query\",
            \"input\": {
                \"user_id\": \"verify_user\",
                \"session_id\": \"$SESSION_ID\",
                \"message\": \"Hello, are you online and what is your name?\"
            }
          }"
    else
        echo "ERROR: Failed to get Session ID"
    fi
    echo -e "\n"
}

test_agent "Orders Analyst" "$ORDERS_RESOURCE"
test_agent "Inventory Analyst" "$INVENTORY_RESOURCE"
