"""A2A Bridge for Gemini Data Analytics agents."""

import os

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from google.cloud import geminidataanalytics_v1beta as geminidataanalytics

# Load environment variables
load_dotenv()

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "global")
AGENT_ORDERS_ID = os.getenv("AGENT_ORDERS_ID")
AGENT_INVENTORY_ID = os.getenv("AGENT_INVENTORY_ID")

app = FastAPI()

# Agent Configs
AGENTS = {
    "orders": {
        "id": AGENT_ORDERS_ID,
        "name": "Order & User Analyst",
        "description": "Expert in customer journeys, order statuses, and site events.",
        "skills": [
            {
                "id": "orders",
                "name": "Order Tracking",
                "description": "Analyze orders and items",
            },
            {
                "id": "users",
                "name": "User Analysis",
                "description": "Analyze customer profiles and events",
            },
        ],
    },
    "inventory": {
        "id": AGENT_INVENTORY_ID,
        "name": "Inventory & Product Analyst",
        "description": "Expert in stock levels, product catalog, and distribution logistics.",
        "skills": [
            {
                "id": "inventory",
                "name": "Inventory Levels",
                "description": "Track stock and distribution centers",
            },
            {
                "id": "products",
                "name": "Product Catalog",
                "description": "Search and analyze product details",
            },
        ],
    },
}


def get_ca_client() -> geminidataanalytics.DataChatServiceClient:
    """Return a DataChatServiceClient instance."""
    return geminidataanalytics.DataChatServiceClient()


async def proxy_to_ca_api(agent_id: str, user_query: str) -> str:
    """Proxy a user query to the Conversational Analytics API.

    Args:
        agent_id: The ID of the data agent to use.
        user_query: The natural language query from the user.

    Returns:
        The text response from the agent.
    """
    client = get_ca_client()
    parent = f"projects/{PROJECT_ID}/locations/{LOCATION}"

    # Create the user message
    messages = [
        geminidataanalytics.Message(
            user_message=geminidataanalytics.UserMessage(text=user_query)
        )
    ]

    # Create the data agent context
    data_agent_context = geminidataanalytics.DataAgentContext(
        data_agent=client.data_agent_path(PROJECT_ID, LOCATION, agent_id),
    )

    # Form the request
    request = geminidataanalytics.ChatRequest(
        parent=parent,
        messages=messages,
        data_agent_context=data_agent_context,
    )

    try:
        # Make the request (streaming)
        stream = client.chat(request=request)

        full_text = ""
        for response in stream:
            if response.system_message and "text" in response.system_message:
                # The SDK response object structure depends on the exact version,
                # based on the intro script: resp.parts is used.
                parts = response.system_message.text.parts
                full_text += "".join(parts)
    except Exception as e:
        print(f"Error proxying to CA API: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    return full_text


# --- A2A Endpoints for Orders Agent ---


@app.get("/orders")
async def orders_card(request: Request) -> dict:
    """Return the A2A agent card for the Orders agent."""
    base_url = str(request.base_url).rstrip("/")
    return {
        "protocolVersion": "0.3.0",
        "name": AGENTS["orders"]["name"],
        "description": AGENTS["orders"]["description"],
        "url": f"{base_url}/orders/chat",
        "version": "1.0.0",
        "capabilities": {},
        "skills": AGENTS["orders"]["skills"],
        "defaultInputModes": ["text/plain"],
        "defaultOutputModes": ["text/plain"],
    }


@app.post("/orders/chat")
async def orders_chat(request: Request) -> dict:
    """Handle chat requests for the Orders agent."""
    body = await request.json()
    user_message = body.get("message", {}).get("text", "")

    if not user_message:
        raise HTTPException(status_code=400, detail="No message provided")

    response_text = await proxy_to_ca_api(AGENTS["orders"]["id"], user_message)

    return {"message": {"text": response_text}}


# --- A2A Endpoints for Inventory Agent ---


@app.get("/inventory")
async def inventory_card(request: Request) -> dict:
    """Return the A2A agent card for the Inventory agent."""
    base_url = str(request.base_url).rstrip("/")
    return {
        "protocolVersion": "0.3.0",
        "name": AGENTS["inventory"]["name"],
        "description": AGENTS["inventory"]["description"],
        "url": f"{base_url}/inventory/chat",
        "version": "1.0.0",
        "capabilities": {},
        "skills": AGENTS["inventory"]["skills"],
        "defaultInputModes": ["text/plain"],
        "defaultOutputModes": ["text/plain"],
    }


@app.post("/inventory/chat")
async def inventory_chat(request: Request) -> dict:
    """Handle chat requests for the Inventory agent."""
    body = await request.json()
    user_message = body.get("message", {}).get("text", "")

    if not user_message:
        raise HTTPException(status_code=400, detail="No message provided")

    response_text = await proxy_to_ca_api(AGENTS["inventory"]["id"], user_message)

    return {"message": {"text": response_text}}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
