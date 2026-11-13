#!/usr/bin/env python3
"""Reproducible audit, cost attribution, and verification CLI for BigQuery Conversational Analytics.

Verifies end-to-end:
  1. BigQuery job label attribution (ca-bq-job=true, data-agent-id=<id>, plus
     custom ADK bqca-role / bqca-user-hash labels) via INFORMATION_SCHEMA.JOBS_BY_PROJECT.
  2. Cloud Audit Logs (geminidataanalytics.googleapis.com) Data Access telemetry,
     grouping by method and channel (A2A vs direct API/console).
  3. Optional live end-to-end chat turn and bounded BigQuery job correlation.

Usage:
    export GOOGLE_CLOUD_PROJECT=your-project-id
    python3 scripts/verify_bqca_audit.py                       # telemetry audit only
    python3 scripts/verify_bqca_audit.py --live \
        --agent order_data_agent \
        --question "How many completed orders were placed?"   # + live turn
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from typing import Any, Sequence

# Make project packages importable regardless of working directory
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import google.api_core.exceptions  # noqa: E402
import google.auth.exceptions  # noqa: E402
from google.cloud import bigquery  # noqa: E402

from semantic.ca_trust import (  # noqa: E402
    build_stateless_chat_request,
    create_chat_client,
    stream_stateless_chat,
)

logger = logging.getLogger("verify_bqca_audit")

PROJECT_PATTERN = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
REGION_PATTERN = re.compile(r"^region-[a-z0-9-]+$")


def build_parser() -> argparse.ArgumentParser:
    """Builds the argument parser for verify_bqca_audit CLI."""
    parser = argparse.ArgumentParser(
        description="Verify BigQuery Conversational Analytics job labels, audit logs, and cost attribution.",
    )
    parser.add_argument(
        "--project",
        default=os.getenv("GOOGLE_CLOUD_PROJECT"),
        help="Google Cloud project ID (defaults to GOOGLE_CLOUD_PROJECT env var).",
    )
    parser.add_argument(
        "--bq-region",
        default="region-us",
        help="BigQuery INFORMATION_SCHEMA region qualifier (e.g. region-us, region-asia-southeast1). Default: region-us.",
    )
    parser.add_argument(
        "--location",
        default=os.getenv("GOOGLE_CLOUD_LOCATION", "global"),
        help="Conversational Analytics API location (e.g. global, us, eu). Default: global.",
    )
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=35,
        help="Number of days of job history and audit logs to inspect (1..180). Default: 35.",
    )
    parser.add_argument(
        "--tib-rate-usd",
        type=float,
        default=6.25,
        help="List rate in USD per TiB for On-Demand compute estimates. Default: 6.25.",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Execute a live stateless chat turn and correlate the executed BigQuery job via bounded polling.",
    )
    parser.add_argument(
        "--agent",
        default="order_data_agent",
        help="Target data agent ID for the live chat turn. Default: order_data_agent.",
    )
    parser.add_argument(
        "--question",
        default="How many completed orders were placed?",
        help="Prompt question to send during the live chat turn.",
    )
    parser.add_argument(
        "--poll-timeout-seconds",
        type=int,
        default=15,
        help="Maximum seconds to poll INFORMATION_SCHEMA for the correlated live job. Default: 15.",
    )
    return parser


def prove_labels(
    client: bigquery.Client,
    project: str,
    bq_region: str,
    lookback_days: int = 35,
    tib_rate_usd: float = 6.25,
) -> list[dict[str, Any]]:
    """Q1/Q3: Audits BigQuery job labels and aggregates per-agent / per-role usage."""
    logger.info("== Proof 1: BigQuery INFORMATION_SCHEMA.JOBS Labels & Cost Attribution ==")
    # Table qualifier cannot be parameterized in BigQuery SQL, but bq_region is validated by REGION_PATTERN
    query = f"""
        SELECT
          COALESCE(
            (SELECT value FROM UNNEST(labels) WHERE key = 'data-agent-id'),
            '(adk-direct)'
          ) AS data_agent_id,
          (SELECT value FROM UNNEST(labels) WHERE key = 'bqca-role') AS bqca_role,
          (SELECT value FROM UNNEST(labels) WHERE key = 'bqca-user-hash') AS bqca_user_hash,
          COUNT(1) AS jobs,
          SUM(total_bytes_billed) AS bytes_billed,
          ROUND(SAFE_DIVIDE(SUM(total_bytes_billed), POW(1024, 4)) * @tib_rate_usd, 4) AS est_cost_usd
        FROM `{bq_region}.INFORMATION_SCHEMA.JOBS_BY_PROJECT`
        WHERE creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @lookback_days DAY)
          AND statement_type IS DISTINCT FROM 'SCRIPT'
          AND (
            EXISTS (SELECT 1 FROM UNNEST(labels) l WHERE l.key = 'ca-bq-job' AND l.value = 'true')
            OR EXISTS (SELECT 1 FROM UNNEST(labels) l WHERE l.key = 'bqca-role')
          )
        GROUP BY data_agent_id, bqca_role, bqca_user_hash
        ORDER BY jobs DESC
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("lookback_days", "INT64", lookback_days),
            bigquery.ScalarQueryParameter("tib_rate_usd", "FLOAT64", tib_rate_usd),
        ]
    )
    try:
        query_job = client.query(query, job_config=job_config, project=project)
        rows = [dict(row.items()) for row in query_job.result()]
    except (google.api_core.exceptions.GoogleAPICallError, google.auth.exceptions.GoogleAuthError) as exc:
        logger.error("Failed to query %s.INFORMATION_SCHEMA.JOBS_BY_PROJECT: %s", bq_region, exc)
        raise

    if not rows:
        logger.warning(
            "Found 0 ca-bq-job or bqca-role jobs in %s over the last %d days.\n"
            "NOTE: Ensure --bq-region (currently '%s') matches the execution region of your dataset\n"
            "(e.g., 'region-us', 'region-eu', 'region-asia-southeast1').",
            bq_region,
            lookback_days,
            bq_region,
        )
        return []

    total_jobs = sum(int(r.get("jobs") or 0) for r in rows)
    logger.info("Found %d agent query jobs across %d label groups (last %dd):", total_jobs, len(rows), lookback_days)
    for r in rows:
        role_info = f" [role={r['bqca_role']}]" if r.get("bqca_role") else ""
        total_bytes = r.get("bytes_billed") or r.get("total_bytes") or 0
        est_cost = r.get("est_cost_usd") or 0.0
        logger.info(
            "  %-35s jobs=%4d  bytes=%12s  cost≈$%s%s",
            r.get("data_agent_id", "unknown"),
            r.get("jobs", 0),
            f"{total_bytes:,}",
            f"{est_cost:.4f}",
            role_info,
        )
    return rows


def prove_audit_logs(
    project: str,
    lookback_days: int = 35,
) -> dict[str, int]:
    """Proof 2: Audits Cloud Audit Logs for Conversational Analytics API interactions."""
    logger.info("== Proof 2: Cloud Audit Logs (geminidataanalytics.googleapis.com) ==")
    if not shutil.which("gcloud"):
        logger.warning("gcloud CLI is not installed or not in PATH; skipping Cloud Audit Log check.")
        return {}

    cmd = [
        "gcloud",
        "logging",
        "read",
        'protoPayload.serviceName="geminidataanalytics.googleapis.com"',
        f"--project={project}",
        f"--freshness={lookback_days}d",
        "--limit=1000",
        "--format=json",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except OSError as exc:
        logger.warning("Failed to execute gcloud logging: %s", exc)
        return {}

    if proc.returncode != 0:
        logger.warning("gcloud logging read returned non-zero exit code %d: %s", proc.returncode, proc.stderr.strip())
        return {}

    stdout = proc.stdout
    idx = stdout.find("[")
    if idx == -1:
        entries = []
    else:
        try:
            entries = json.loads(stdout[idx:])
        except json.JSONDecodeError:
            entries = []

    if len(entries) >= 1000:
        logger.warning(
            "Fetched 1000 Cloud Audit Log entries (--limit=1000 cap reached); "
            "counts below reflect the most recent 1000 entries only."
        )

    if not entries:
        logger.warning(
            "No Cloud Audit Log entries found for service 'geminidataanalytics.googleapis.com' (last %dd).\n"
            "NOTE: Data Access audit logs (DATA_READ / DATA_WRITE) for geminidataanalytics.googleapis.com\n"
            "are NOT enabled by default in Google Cloud IAM. Enable them in Cloud Console under:\n"
            "  IAM & Admin -> Audit Logs -> Conversational Analytics API (geminidataanalytics.googleapis.com) -> Check Data Read & Data Write.\n"
            "Also note: 'ca-bq-job' and 'data-agent-id' are observed BigQuery service job labels.",
            lookback_days,
        )
        return {}

    tally: dict[str, int] = {}
    for entry in entries:
        payload = entry.get("protoPayload", {})
        method = payload.get("methodName", "(unknown)")
        tally[method] = tally.get(method, 0) + 1

    for method, count in sorted(tally.items(), key=lambda x: -x[1]):
        channel = "GEMINI ENTERPRISE (A2A)" if "A2AService" in method else "direct API/console"
        logger.info("  %4d  %-50s [%s]", count, method, channel)

    return tally


def prove_live(
    client: bigquery.Client,
    project: str,
    agent: str,
    question: str,
    location: str = "global",
    bq_region: str = "region-us",
    poll_timeout_seconds: int = 15,
) -> list[dict[str, Any]]:
    """Proof 3: Live chat turn with bounded polling for correlated BigQuery job execution."""
    logger.info("== Proof 3: Live End-to-End Chat & Bounded BigQuery Job Correlation ==")
    chat_client = create_chat_client(location=location)
    data_agent_name = f"projects/{project}/locations/{location}/dataAgents/{agent}"
    req = build_stateless_chat_request(
        project_id=project,
        data_agent_name=data_agent_name,
        question=question,
        location=location,
    )

    start_time = datetime.now(timezone.utc)
    logger.info("Sending chat turn to data agent '%s' (question: '%s')...", agent, question)
    assessment = stream_stateless_chat(
        client=chat_client,
        request=req,
        question=question,
    )
    logger.info("Stream trust assessment tier: %s (sub_mode: %s)", assessment.tier.value, assessment.sub_mode)
    if assessment.final_sql:
        logger.info("Stream emitted SQL: %s", assessment.final_sql.strip())
    if assessment.reasons:
        logger.info("Assessment reasons: %s", assessment.reasons)

    logger.info(
        "Polling %s.INFORMATION_SCHEMA.JOBS_BY_PROJECT for correlated query job (timeout=%ds)...",
        bq_region,
        poll_timeout_seconds,
    )

    query = f"""
        SELECT
          job_id,
          creation_time,
          statement_type,
          total_bytes_billed,
          (SELECT value FROM UNNEST(labels) WHERE key = 'ca-bq-job') AS ca_bq_job,
          (SELECT value FROM UNNEST(labels) WHERE key = 'data-agent-id') AS data_agent_id,
          (SELECT value FROM UNNEST(labels) WHERE key = 'bqca-role') AS bqca_role
        FROM `{bq_region}.INFORMATION_SCHEMA.JOBS_BY_PROJECT`
        WHERE creation_time >= @start_time
          AND statement_type IS DISTINCT FROM 'SCRIPT'
          AND EXISTS (
            SELECT 1 FROM UNNEST(labels) l
            WHERE l.key = 'data-agent-id' AND l.value = @agent_id
          )
        ORDER BY creation_time DESC
        LIMIT 5
    """

    deadline = time.time() + poll_timeout_seconds
    matched_rows: list[dict[str, Any]] = []

    while time.time() < deadline:
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("start_time", "TIMESTAMP", start_time),
                bigquery.ScalarQueryParameter("agent_id", "STRING", agent),
            ]
        )
        try:
            q_job = client.query(query, job_config=job_config, project=project)
            rows = [dict(row.items()) for row in q_job.result()]
            if rows:
                matched_rows = rows
                break
        except Exception as exc:
            logger.debug("Polling error (will retry until deadline): %s", exc)

        time.sleep(2.0)

    if matched_rows:
        for r in matched_rows:
            logger.info(
                "  LIVE JOB %s: ca-bq-job=%s data-agent-id=%s role=%s bytes=%s",
                r["job_id"],
                r.get("ca_bq_job"),
                r.get("data_agent_id"),
                r.get("bqca_role"),
                r.get("total_bytes_billed"),
            )
    else:
        logger.warning(
            "No correlated BigQuery job appeared within %d seconds.\n"
            "Possible reasons: query was served from cache, agent used a different dataset region,\n"
            "or the job execution region does not match --bq-region '%s'.",
            poll_timeout_seconds,
            bq_region,
        )

    return matched_rows


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for verify_bqca_audit."""
    parser = build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

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

    if not REGION_PATTERN.match(args.bq_region):
        logger.error(
            "Invalid bq-region identifier '%s'. Must match %s (e.g. region-us, region-eu).",
            args.bq_region,
            REGION_PATTERN.pattern,
        )
        return 1

    if not (1 <= args.lookback_days <= 180):
        logger.error("--lookback-days must be between 1 and 180 (got %d)", args.lookback_days)
        return 1

    if args.tib_rate_usd <= 0:
        logger.error("--tib-rate-usd must be positive (got %f)", args.tib_rate_usd)
        return 1

    if args.poll_timeout_seconds <= 0:
        logger.error("--poll-timeout-seconds must be positive (got %d)", args.poll_timeout_seconds)
        return 1

    try:
        bq_client = bigquery.Client(project=args.project)
    except Exception as exc:
        logger.error("Failed to initialize BigQuery client for project '%s': %s", args.project, exc)
        return 1

    try:
        prove_labels(
            client=bq_client,
            project=args.project,
            bq_region=args.bq_region,
            lookback_days=args.lookback_days,
            tib_rate_usd=args.tib_rate_usd,
        )
    except (google.api_core.exceptions.GoogleAPICallError, google.auth.exceptions.GoogleAuthError) as exc:
        logger.error("Proof 1 failed: %s", exc)
        return 1

    try:
        prove_audit_logs(
            project=args.project,
            lookback_days=args.lookback_days,
        )
    except (google.api_core.exceptions.GoogleAPICallError, google.auth.exceptions.GoogleAuthError) as exc:
        logger.error("Proof 2 failed: %s", exc)
        return 1

    if args.live:
        try:
            live_rows = prove_live(
                client=bq_client,
                project=args.project,
                agent=args.agent,
                question=args.question,
                location=args.location,
                bq_region=args.bq_region,
                poll_timeout_seconds=args.poll_timeout_seconds,
            )
            if not live_rows:
                logger.error("Proof 3 failed: no correlated BigQuery job appeared within timeout.")
                return 1
        except (google.api_core.exceptions.GoogleAPICallError, google.auth.exceptions.GoogleAuthError) as exc:
            logger.error("Proof 3 failed: %s", exc)
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
