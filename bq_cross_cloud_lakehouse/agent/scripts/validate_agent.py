"""Validate the Froyo Lakehouse CA data agent against the demo storyline.

Sends the Midnight Swirl storyline questions from ``DEMO_RUNDOWN.md`` to the
data agent through the CA API ``:chat`` endpoint and prints the text answers,
generated SQL, and row counts. Use it to confirm SQL generation and the
cross-cloud join before presenting in Gemini Enterprise.

Usage::

    uv run python scripts/validate_agent.py
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

_AGENT_ROOT = Path(__file__).resolve().parents[1]
_DEMO_CONFIG = _AGENT_ROOT.parent / "config.local.env"
_AGENT_ENV = _AGENT_ROOT / ".env"

if _DEMO_CONFIG.exists():
    load_dotenv(_DEMO_CONFIG, override=False)
if _AGENT_ENV.exists():
    load_dotenv(_AGENT_ENV, override=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

PROJECT_ID = os.getenv("GCP_PROJECT") or os.getenv("GOOGLE_CLOUD_PROJECT", "")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "global")
AGENT_ID = os.getenv("AGENT_ID", "froyo_lakehouse_agent")

# Storyline questions (see DEMO_RUNDOWN.md).
QUESTIONS = [
    ("Show total Midnight Swirl revenue by region, highest first."),
    (
        "What allergens are in Midnight Swirl, and which supplier document "
        "reveals each one?"
    ),
    (
        "Build a Midnight Swirl campaign target list from our loyalty customers "
        "whose favorite flavor is Midnight Swirl, excluding soy-sensitive "
        "customers. Show customer_id, region, loyalty_tier, and avg_monthly_spend, "
        "ordered by avg_monthly_spend descending."
    ),
    (
        "Which region has the highest total Midnight Swirl revenue over the last "
        "12 months, and show the monthly revenue trend per region."
    ),
    (
        "Summarize today's findings into an executive-ready slide outline: "
        "(1) allergen risk for Midnight Swirl, (2) the cross-cloud soy-safe "
        "target list, and (3) regional revenue performance. End with a slide on "
        "the data governance guardrails."
    ),
]


def ca_api_base(location: str) -> str:
    """Return the CA API base URL for the given resource location.

    Args:
        location: CA API resource location.

    Returns:
        The matching CA API base URL.
    """
    if not location or location == "global":
        return "https://geminidataanalytics.googleapis.com"
    if "-" in location:
        return f"https://geminidataanalytics-{location}.googleapis.com"
    return f"https://geminidataanalytics.{location}.rep.googleapis.com"


def get_access_token() -> str:
    """Get an access token from the gcloud CLI.

    Returns:
        Bearer token string.

    Raises:
        RuntimeError: If the gcloud command fails.
    """
    result = subprocess.run(
        ["gcloud", "auth", "print-access-token"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to get access token: {result.stderr.strip()}")
    return result.stdout.strip()


def ask_agent(agent_id: str, question: str, token: str) -> None:
    """Send a question to the CA API agent and print the streamed response.

    Args:
        agent_id: The CA API data agent id.
        question: Natural-language question.
        token: Bearer access token.

    Raises:
        RuntimeError: If the API request fails.
    """
    base = f"{ca_api_base(LOCATION)}/v1beta"
    data_agent_name = (
        f"projects/{PROJECT_ID}/locations/{LOCATION}/dataAgents/{agent_id}"
    )
    chat_url = f"{base}/projects/{PROJECT_ID}/locations/{LOCATION}:chat"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messages": [{"userMessage": {"text": question}}],
        "dataAgentContext": {"dataAgent": data_agent_name},
    }

    with requests.post(chat_url, json=payload, headers=headers, stream=True) as resp:
        if resp.status_code != 200:
            logger.error("HTTP %s: %s", resp.status_code, resp.text[:300])
            raise RuntimeError(f"API request failed with status {resp.status_code}")

        accumulator = ""
        for line in resp.iter_lines():
            if not line:
                continue
            decoded = line.decode("utf-8")

            if decoded == "[{":
                accumulator = "{"
            elif decoded == "}]":
                accumulator += "}"
            elif decoded == ",":
                continue
            else:
                accumulator += decoded

            try:
                data_json = json.loads(accumulator)
            except ValueError:
                continue

            if "error" in data_json:
                logger.error("API error: %s", data_json["error"])
                accumulator = ""
                continue

            msg = data_json.get("systemMessage")
            if not msg:
                accumulator = ""
                continue

            if "text" in msg:
                text = "".join(msg["text"].get("parts", []))
                if text.strip():
                    print(f"  [TEXT] {text[:500]}")

            if "data" in msg:
                data = msg["data"]
                if "generatedSql" in data:
                    print(f"\n  [SQL] {data['generatedSql'][:400]}\n")
                if "result" in data:
                    rows = data["result"].get("data", [])
                    print(f"  [RESULT] {len(rows)} rows returned")
                    for row in rows[:5]:
                        print(f"    {row}")
                    if len(rows) > 5:
                        print(f"    ... and {len(rows) - 5} more rows")

            accumulator = ""


def main() -> None:
    """Run the storyline validation questions against the agent."""
    if not PROJECT_ID:
        raise ValueError("GCP_PROJECT must be set.")

    token = get_access_token()
    total = len(QUESTIONS)
    passed = 0
    failed = 0

    print(f"\n{'=' * 60}")
    print(f"Agent: {AGENT_ID}  (project={PROJECT_ID}, location={LOCATION})")
    print(f"{'=' * 60}")

    for i, question in enumerate(QUESTIONS, 1):
        print(f"\n--- Q{i}: {question}")
        try:
            ask_agent(AGENT_ID, question, token)
            passed += 1
        except Exception as e:  # noqa: BLE001 -- validation harness: report and continue.
            logger.error("Failed on Q%d: %s", i, e)
            failed += 1

    print(f"\n{'=' * 60}")
    print(
        f"Froyo Lakehouse validation complete: {passed}/{total} passed, {failed} failed"
    )
    print(f"{'=' * 60}")

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
