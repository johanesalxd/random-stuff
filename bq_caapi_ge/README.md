# Gemini Conversational Analytics A2A Demo

This project demonstrates how to bridge Google Cloud's **Conversational Analytics API** with **Gemini Enterprise** using the **Agent-to-Agent (A2A) Protocol**.

## Architecture Overview

The following diagram illustrates how user queries flow from the Gemini Enterprise web app to BigQuery through our A2A bridge.

```mermaid
sequenceDiagram
    participant User
    participant GE as Gemini Enterprise
    participant Bridge as A2A Bridge
    participant CA as CA API
    participant BQ as BigQuery

    User->>GE: Asks a data question
    GE->>Bridge: POST /chat
    Bridge->>CA: client.chat()
    CA->>BQ: Executes SQL
    BQ-->>CA: Returns data
    CA-->>Bridge: Returns answer
    Bridge-->>GE: Returns JSON
    GE-->>User: Displays answer
```

## Project Structure

```text
├── app/
│   └── bridge.py          # A2A Bridge FastAPI server
├── scripts/
│   ├── admin_tools.py      # Data Agent lifecycle management
│   ├── cleanup_and_list.py # Agent cleanup and inspection utility
│   └── register_agents.py  # A2A registration utility
├── tests/
│   └── test_bridge.py      # Integration tests for the bridge
├── docs/
│   └── reference/          # API references and links
├── .env                    # Local environment variables
└── README.md               # Project documentation
```

## Core Components

### 1. Admin & Setup
*   `scripts/admin_tools.py`: Configures the backend Data Agents. It splits the `thelook_ecommerce` dataset into two specialized agents:
    *   **Agent A**: Orders & Users
    *   **Agent B**: Inventory & Products
*   `scripts/cleanup_and_list.py`: Utility to list all agents and their configurations or delete unnecessary ones.

### 2. The Bridge
*   `app/bridge.py`: A FastAPI server that implements the A2A Protocol. It exposes two virtual agents:
    *   `GET /orders`: Discovery endpoint for Agent A.
    *   `GET /inventory`: Discovery endpoint for Agent B.
    *   `POST /orders/chat` & `POST /inventory/chat`: Proxy endpoints for natural language processing.

### 3. Verification & Registration
*   `tests/test_bridge.py`: Local testing script to verify the bridge can communicate with the CA API and return correct answers.
*   `scripts/register_agents.py`: Automates the registration of the A2A Bridge endpoints into a Gemini Enterprise App.

## Getting Started

### Prerequisites
*   Python 3.11+
*   `uv` (package manager)
*   Google Cloud Project with Gemini Data Analytics and Discovery Engine APIs enabled.

### Setup

1.  **Install dependencies:**
    ```bash
    uv sync
    ```

2.  **Configure Environment:**
    Copy `.env.example` to `.env` and fill in your project details.
    ```bash
    cp .env.example .env
    ```

3.  **Setup Backend Agents:**

    Choose the scenario that matches your current state:

    *   **Scenario A: Demo Setup (Recommended)**
        You have one agent created in the BigQuery Console (Agent A) and need to create the second agent (Agent B) programmatically while updating Agent A's context.
        ```bash
        uv run python scripts/admin_tools.py
        ```

    *   **Scenario B: Agents Already Exist**
        If you have already created both agents manually in the BigQuery Console or have run the setup script previously:
        1.  **Skip** the `admin_tools.py` script.
        2.  Ensure your `.env` file contains the correct IDs for `AGENT_ORDERS_ID` and `AGENT_INVENTORY_ID`.
        3.  Proceed to Step 4.

4.  **Run the Bridge:**
    ```bash
    uv run python app/bridge.py
    ```

5.  **Expose and Register:**
    Use a tunnel (like `ngrok`) to expose port 8000 and run the registration script:
    ```bash
    uv run python scripts/register_agents.py https://<your-public-url>
    ```

## Deployment

### Cloud Run (Production)

The bridge is designed to be deployed to **Google Cloud Run** using **Cloud Build**. This demo uses **OAuth Passthrough**, allowing BigQuery to see the actual user identity.

1.  **Deploy to Cloud Run:**
    ```bash
    gcloud run deploy bq-caapi-bridge \
      --source . \
      --region us-central1 \
      --allow-unauthenticated \
      --set-env-vars GOOGLE_CLOUD_PROJECT=your-project-id,GOOGLE_CLOUD_LOCATION=global,AGENT_ORDERS_ID=your-id,AGENT_INVENTORY_ID=your-id,BIGQUERY_DATASET_ID=thelook_ecommerce
    ```

2.  **Register with OAuth:**
    The `register_agents.py` script automatically configures the OAuth handshake if the authorization resources are created.
    ```bash
    uv run python scripts/register_agents.py https://<your-cloud-run-url>
    ```

## Security & Identity

### OAuth Passthrough
This demo implements **User Identity Passthrough**. When a user chats with the agent in Gemini Enterprise:
1.  Gemini Enterprise performs an OAuth handshake with the user.
2.  The user's access token is passed to the **A2A Bridge**.
3.  The Bridge initializes the CA API client using this token.
4.  BigQuery executes the query using the **User's Identity**, enabling Row-Level Security (RLS) and audit logging.

### IAM Notes
*   **Demo Simplicity:** For this demo, the Service Account and Users are assumed to have `Project Editor` or equivalent permissions.
*   **Production Best Practice:** In a real-world scenario, you should implement **Least Privilege**:
    *   **Service Account:** Should only have `Discovery Engine Admin` (for registration) and `Cloud Run Invoker`.
    *   **Users:** Should have `BigQuery Data Viewer` and `Conversational Analytics User` roles.
*   **Public Ingress:** The Cloud Run service is currently `--allow-unauthenticated` so Gemini Enterprise can reach it. For production, consider using Google Cloud API Gateway or specialized ingress controls.

## Code Standards
This project follows the Google Python Style Guide and utilizes `ruff` for linting and formatting. Documentation follows `JSDoc`/`Docstring` requirements as specified in the project's global standards.
