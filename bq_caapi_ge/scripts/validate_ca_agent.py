#!/usr/bin/env python3
"""CLI regression and trust-tier validator for Conversational Analytics Data Agents.

Validates live or mock Conversational Analytics data agents against expected questions,
evaluating response trust tiers (Tier 1 Verified/Compiled, Tier 2 Grounded, Tier 3 Review Required),
prose-to-row numeric consistency, and generated SQL.

Usage:
    export GOOGLE_CLOUD_PROJECT=your-project-id
    python3 scripts/validate_ca_agent.py --agent order_data_agent -q "How many orders were placed?"
    python3 scripts/validate_ca_agent.py --questions-file tests/fixtures/questions.yaml --max-tier 2
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path
import re
import sys
from typing import Sequence

# Make project packages importable regardless of working directory
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import google.auth.exceptions  # noqa: E402
from google.cloud import geminidataanalytics_v1beta as geminidataanalytics  # noqa: E402
import yaml  # noqa: E402

from config.ca_locations import ca_api_endpoint  # noqa: E402
from semantic.ca_trust import (  # noqa: E402
    TrustAssessment,
    TrustTier,
    VerifiedQuerySpec,
    build_stateless_chat_request,
    create_chat_client,
    stream_stateless_chat,
)

logger = logging.getLogger("validate_ca_agent")

PROJECT_PATTERN = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
AGENT_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,128}$")

DEFAULT_TEXT_LIMIT = 600
DEFAULT_SQL_LIMIT = 400
DEFAULT_ROW_LIMIT = 5

TIER_RANK: dict[TrustTier, int] = {
    TrustTier.TIER_1_VERIFIED_OR_COMPILED: 1,
    TrustTier.TIER_2_GROUNDED: 2,
    TrustTier.TIER_3_REVIEW_REQUIRED: 3,
}


def build_parser() -> argparse.ArgumentParser:
    """Builds the argument parser for validate_ca_agent CLI."""
    parser = argparse.ArgumentParser(
        description="Regression and trust-tier validator for Conversational Analytics Data Agents.",
    )
    parser.add_argument(
        "--project",
        default=os.getenv("GOOGLE_CLOUD_PROJECT"),
        help="Google Cloud project ID (defaults to GOOGLE_CLOUD_PROJECT env var).",
    )
    parser.add_argument(
        "--location",
        default=os.getenv("GOOGLE_CLOUD_LOCATION", "global"),
        help="Conversational Analytics API location (e.g. global, us, eu). Default: global.",
    )
    parser.add_argument(
        "--agent",
        help="Target data agent ID (required unless questions-file provides suites with agent_id).",
    )
    parser.add_argument(
        "-q",
        "--question",
        action="append",
        dest="questions",
        help="Prompt question to validate (repeatable for multiple questions).",
    )
    parser.add_argument(
        "--questions-file",
        help="Path to YAML or JSON file containing questions or question suites.",
    )
    parser.add_argument(
        "--verified-queries",
        help="Path to JSON file exported by scripts/export_semantic_layer.py --format verified-queries.",
    )
    parser.add_argument(
        "--impersonate-role",
        help="Role slug for Layer-3 IAM service account impersonation (cannot be used with CA_USER_ACCESS_TOKEN).",
    )
    parser.add_argument(
        "--max-tier",
        type=int,
        choices=[1, 2, 3],
        default=3,
        help=(
            "Maximum acceptable trust tier number (1=Verified/Compiled [strictest], "
            "2=Grounded, 3=Review Required [permissive]). For example, --max-tier 2 fails "
            "if any response drops to TIER_3_REVIEW_REQUIRED."
        ),
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Disable truncation for SQL, prose, and result rows in output.",
    )
    return parser


def load_questions(
    questions_arg: Sequence[str] | None,
    questions_file_path: str | None,
    default_agent: str | None,
) -> list[tuple[str, list[tuple[str, str]]]]:
    """Loads suites of (agent_id, [(question, expected_note), ...])."""
    suites: list[tuple[str, list[tuple[str, str]]]] = []

    if questions_arg:
        if not default_agent:
            raise ValueError("--agent must be specified when using -q/--question.")
        q_list = [(q, "") for q in questions_arg]
        suites.append((default_agent, q_list))

    if questions_file_path:
        p = Path(questions_file_path)
        if not p.is_file():
            raise FileNotFoundError(f"Questions file not found: {questions_file_path}")
        with p.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if isinstance(data, list):
            # Flat list of questions
            if not default_agent:
                raise ValueError("--agent must be specified when questions-file contains a flat list.")
            items: list[tuple[str, str]] = []
            for item in data:
                if isinstance(item, str):
                    items.append((item, ""))
                elif isinstance(item, dict):
                    q = item.get("question") or item.get("prompt") or ""
                    note = item.get("expected_note") or item.get("expected") or ""
                    if q:
                        items.append((q, note))
            suites.append((default_agent, items))
        elif isinstance(data, dict):
            if "suites" in data and isinstance(data["suites"], list):
                for suite in data["suites"]:
                    agent_id = suite.get("agent_id") or default_agent
                    if not agent_id:
                        raise ValueError("Suite missing 'agent_id' and no default --agent specified.")
                    items = []
                    for item in suite.get("questions", []):
                        if isinstance(item, str):
                            items.append((item, ""))
                        elif isinstance(item, dict):
                            q = item.get("question") or item.get("prompt") or ""
                            note = item.get("expected_note") or item.get("expected") or ""
                            if q:
                                items.append((q, note))
                    if items:
                        suites.append((agent_id, items))
            else:
                raise ValueError("Unrecognized questions-file dictionary format; expected 'suites' key.")

    return suites


def load_verified_queries(path: str | None) -> list[VerifiedQuerySpec]:
    """Loads verified query specs from an exported JSON file."""
    if not path:
        return []
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Verified queries file not found: {path}")
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON list of verified queries in {path}")
    specs: list[VerifiedQuerySpec] = []
    for item in data:
        if isinstance(item, dict) and "question" in item and "sql" in item:
            specs.append(
                VerifiedQuerySpec(
                    question=item["question"],
                    sql=item["sql"],
                    query_id=item.get("query_id"),
                )
            )
    return specs


def get_chat_client(
    location: str,
    project: str,
    impersonate_role: str | None,
    user_access_token: str | None,
) -> geminidataanalytics.DataChatServiceClient:
    """Builds a configured DataChatServiceClient respecting impersonation or user OAuth token."""
    del project  # Maintained for signature compatibility; client routing is driven by location.
    if impersonate_role:
        return create_chat_client(
            location=location,
            impersonated_role=impersonate_role,
        )
    if user_access_token:
        return create_chat_client(
            location=location,
            user_access_token=user_access_token,
        )
    return create_chat_client(location=location)


def format_output(
    assessment: TrustAssessment,
    expected_note: str,
    full: bool,
) -> str:
    """Formats assessment output with optional truncation."""
    text_lim = 0 if full else DEFAULT_TEXT_LIMIT
    sql_lim = 0 if full else DEFAULT_SQL_LIMIT
    row_lim = 0 if full else DEFAULT_ROW_LIMIT

    lines: list[str] = [
        f"  Trust Tier : {assessment.tier.value} (sub_mode: {assessment.sub_mode})",
    ]
    if expected_note:
        lines.append(f"  Expected   : {expected_note}")
    if assessment.reasons:
        lines.append(f"  Reasons    : {'; '.join(assessment.reasons)}")

    if assessment.final_sql:
        sql = assessment.final_sql.strip()
        if sql_lim and len(sql) > sql_lim:
            sql = sql[:sql_lim] + " ... [truncated]"
        lines.append(f"  SQL        :\n    {sql}")

    if assessment.final_response:
        resp = assessment.final_response.strip()
        if text_lim and len(resp) > text_lim:
            resp = resp[:text_lim] + " ... [truncated]"
        lines.append(f"  Response   :\n    {resp}")

    if assessment.result_rows:
        total_rows = len(assessment.result_rows)
        lines.append(f"  Result Rows: {total_rows} row(s)")
        shown_rows = assessment.result_rows if row_lim == 0 else assessment.result_rows[:row_lim]
        for r in shown_rows:
            lines.append(f"    {dict(r)}")
        if row_lim and total_rows > row_lim:
            lines.append(f"    ... and {total_rows - row_lim} more row(s)")

    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for validate_ca_agent."""
    parser = build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    user_token = os.getenv("CA_USER_ACCESS_TOKEN")
    if user_token and args.impersonate_role:
        logger.error(
            "Mutual exclusion violation: Cannot set both CA_USER_ACCESS_TOKEN environment variable "
            "and --impersonate-role CLI flag."
        )
        return 1

    if not args.project:
        logger.error("GOOGLE_CLOUD_PROJECT environment variable or --project flag is required.")
        return 1

    if not PROJECT_PATTERN.match(args.project):
        logger.error(
            "Invalid project identifier '%s'. Must match %s",
            args.project,
            PROJECT_PATTERN.pattern,
        )
        return 1

    if args.agent and not AGENT_PATTERN.match(args.agent):
        logger.error(
            "Invalid agent identifier '%s'. Must match %s",
            args.agent,
            AGENT_PATTERN.pattern,
        )
        return 1

    try:
        suites = load_questions(args.questions, args.questions_file, args.agent)
    except (ValueError, FileNotFoundError) as exc:
        logger.error("Failed to load questions: %s", exc)
        return 1

    if not suites:
        logger.error("No questions specified. Provide -q/--question or --questions-file.")
        return 1

    try:
        verified_queries = load_verified_queries(args.verified_queries)
    except (ValueError, FileNotFoundError) as exc:
        logger.error("Failed to load verified queries: %s", exc)
        return 1

    try:
        client = get_chat_client(
            location=args.location,
            project=args.project,
            impersonate_role=args.impersonate_role,
            user_access_token=user_token,
        )
    except (google.auth.exceptions.GoogleAuthError, ValueError) as exc:
        logger.error("Authentication / client initialization failed: %s", exc)
        return 1

    passed_count = 0
    below_tier_count = 0
    errored_count = 0
    total_count = 0

    print("=" * 72)
    print(f"Conversational Analytics Agent Regression Validator (Project: {args.project}, Location: {args.location})")
    print(f"Max Acceptable Tier: {args.max_tier} | Endpoint: {ca_api_endpoint(args.location)}")
    print("=" * 72)

    for agent_id, questions in suites:
        print(f"\n---> Suite: Data Agent [{agent_id}] ({len(questions)} question(s))")
        data_agent_name = f"projects/{args.project}/locations/{args.location}/dataAgents/{agent_id}"

        for idx, (question, expected_note) in enumerate(questions, 1):
            total_count += 1
            print(f"\n[Q{idx}] {question}")
            try:
                req = build_stateless_chat_request(
                    project_id=args.project,
                    data_agent_name=data_agent_name,
                    question=question,
                    location=args.location,
                )
                assessment = stream_stateless_chat(
                    client=client,
                    request=req,
                    question=question,
                    authored_verified_queries=verified_queries,
                )
                print(format_output(assessment, expected_note, args.full))

                achieved_tier = TIER_RANK.get(assessment.tier, 3)
                if achieved_tier <= args.max_tier:
                    print("  Status     : PASS")
                    passed_count += 1
                else:
                    print(f"  Status     : BELOW_TIER (achieved Tier {achieved_tier} > max {args.max_tier})")
                    below_tier_count += 1
            except Exception as exc:
                print(f"  Status     : ERROR ({exc})")
                logger.error("Error evaluating question '%s': %s", question, exc)
                errored_count += 1

    print("\n" + "=" * 72)
    summary_line = (
        f"Validation Complete: {passed_count}/{total_count} passed, "
        f"{below_tier_count} below_tier, {errored_count} errored."
    )
    print(summary_line)
    print("=" * 72)

    return 0 if (below_tier_count == 0 and errored_count == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
