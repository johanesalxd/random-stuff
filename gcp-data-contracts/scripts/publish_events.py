#!/usr/bin/env python3
"""
SGX Equity Trade Event Producer & Data Contract Verification Script.

Demonstrates two-tier Google Cloud Data Contract enforcement:
1. Wire-Level Perimeter Defense: Synchronous INVALID_ARGUMENT rejection via
   Google Cloud Pub/Sub Schema Registry (Avro JSON encoding).
2. Downstream Storage Enforcement: BigQuery Direct Subscription Storage Write
   API failure with automated Dead Letter Queue (DLQ) quarantine.

Features:
- Dual-engine architecture (native google-cloud-pubsub with transparent gcloud subprocess fallback).
- Modes: --mode=valid, --mode=invalid-schema, --mode=trigger-dlq.
- Deterministic exit codes and structured terminal telemetry.
"""

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
import random
import shutil
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Tuple


# ==============================================================================
# Market Data Fixtures & Constants (Global & SGX Presets)
# ==============================================================================

GLOBAL_INSTRUMENTS = [
    {"ticker": "AAPL", "name": "Apple Inc.", "base_price": 224.50},
    {"ticker": "GOOGL", "name": "Alphabet Inc.", "base_price": 178.20},
    {"ticker": "MSFT", "name": "Microsoft Corp.", "base_price": 428.00},
    {"ticker": "NVDA", "name": "NVIDIA Corp.", "base_price": 119.30},
    {"ticker": "AMZN", "name": "Amazon.com Inc.", "base_price": 186.40},
]

SGX_INSTRUMENTS = [
    {"ticker": "D05.SI", "name": "DBS Group Holdings", "base_price": 35.80},
    {"ticker": "Z74.SI", "name": "Singtel", "base_price": 3.15},
    {"ticker": "U11.SI", "name": "United Overseas Bank", "base_price": 32.40},
    {"ticker": "O39.SI", "name": "Oversea-Chinese Banking Corp", "base_price": 15.20},
    {"ticker": "C6L.SI", "name": "Singapore Airlines", "base_price": 6.45},
]

GLOBAL_BUYER_BROKERS = [
    "BROKER_ALPHA_01",
    "BROKER_BETA_01",
    "BROKER_GAMMA_01",
    "BROKER_DELTA_01",
    "BROKER_EPSILON_01",
]

GLOBAL_SELLER_BROKERS = [
    "BROKER_ZETA_02",
    "BROKER_ETA_02",
    "BROKER_THETA_02",
    "BROKER_IOTA_02",
    "BROKER_KAPPA_02",
]

SGX_BUYER_BROKERS = [
    "BROKER_DBS_01",
    "BROKER_UOB_01",
    "BROKER_CITI_01",
    "BROKER_HSBC_01",
    "BROKER_SCB_01",
]

SGX_SELLER_BROKERS = [
    "BROKER_OCBC_02",
    "BROKER_DBS_02",
    "BROKER_SCB_02",
    "BROKER_MAYBANK_01",
    "BROKER_CITI_02",
]

BUYER_BROKERS = SGX_BUYER_BROKERS
SELLER_BROKERS = SGX_SELLER_BROKERS
LOT_SIZES = [100, 500, 1000, 2000, 5000, 10000]


@dataclass
class PublishResult:
    """Standardized publish attempt result across both engines."""
    success: bool
    message_id: Optional[str]
    status_code: int
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    engine_used: str = "unknown"
    latency_ms: float = 0.0


# ==============================================================================
# Dual-Engine Publisher Abstraction
# ==============================================================================

class BasePublisherEngine:
    """Abstract interface for Pub/Sub publishing engines."""
    def publish(self, project_id: str, topic: str, payload: Dict[str, Any]) -> PublishResult:
        raise NotImplementedError


class ClientLibraryEngine(BasePublisherEngine):
    """Native Python google-cloud-pubsub client library engine."""

    def __init__(self):
        from google.cloud import pubsub_v1
        from google.api_core import exceptions as google_exceptions
        self._pubsub_v1 = pubsub_v1
        self._exceptions = google_exceptions
        self._publisher = pubsub_v1.PublisherClient()

    def publish(self, project_id: str, topic: str, payload: Dict[str, Any]) -> PublishResult:
        # Resolve fully qualified topic path
        if topic.startswith("projects/"):
            topic_path = topic
        else:
            topic_path = self._publisher.topic_path(project_id, topic)

        data = json.dumps(payload).encode("utf-8")
        start_time = time.time()

        try:
            future = self._publisher.publish(topic_path, data)
            msg_id = future.result(timeout=15.0)
            latency = (time.time() - start_time) * 1000.0
            return PublishResult(
                success=True,
                message_id=msg_id,
                status_code=200,
                engine_used="google-cloud-pubsub",
                latency_ms=latency,
            )
        except self._exceptions.InvalidArgument as e:
            latency = (time.time() - start_time) * 1000.0
            return PublishResult(
                success=False,
                message_id=None,
                status_code=400,
                error_code="INVALID_ARGUMENT",
                error_message=str(e),
                engine_used="google-cloud-pubsub",
                latency_ms=latency,
            )
        except self._exceptions.PermissionDenied as e:
            latency = (time.time() - start_time) * 1000.0
            return PublishResult(
                success=False,
                message_id=None,
                status_code=403,
                error_code="PERMISSION_DENIED",
                error_message=str(e),
                engine_used="google-cloud-pubsub",
                latency_ms=latency,
            )
        except Exception as e:
            latency = (time.time() - start_time) * 1000.0
            return PublishResult(
                success=False,
                message_id=None,
                status_code=500,
                error_code=type(e).__name__,
                error_message=str(e),
                engine_used="google-cloud-pubsub",
                latency_ms=latency,
            )


class SubprocessGcloudEngine(BasePublisherEngine):
    """Fallback engine using gcloud CLI subprocess execution."""

    def __init__(self):
        gcloud_bin = shutil.which("gcloud")
        if not gcloud_bin:
            raise RuntimeError("gcloud CLI is not installed or not available in PATH")
        self._gcloud_bin = gcloud_bin

    def publish(self, project_id: str, topic: str, payload: Dict[str, Any]) -> PublishResult:
        topic_name = topic.split("/")[-1] if "/" in topic else topic
        payload_str = json.dumps(payload)

        cmd = [
            self._gcloud_bin,
            "pubsub",
            "topics",
            "publish",
            topic_name,
            f"--message={payload_str}",
            f"--project={project_id}",
            "--format=value(messageIds[0])",
        ]

        start_time = time.time()
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        latency = (time.time() - start_time) * 1000.0

        if proc.returncode == 0:
            msg_id = proc.stdout.strip()
            return PublishResult(
                success=True,
                message_id=msg_id if msg_id else "UNKNOWN_MSG_ID",
                status_code=200,
                engine_used="gcloud-subprocess",
                latency_ms=latency,
            )

        stderr = proc.stderr.strip()
        if "INVALID_ARGUMENT" in stderr or "INVALID_JSON_AVRO_MESSAGE" in stderr:
            return PublishResult(
                success=False,
                message_id=None,
                status_code=400,
                error_code="INVALID_ARGUMENT",
                error_message=stderr,
                engine_used="gcloud-subprocess",
                latency_ms=latency,
            )
        elif "PERMISSION_DENIED" in stderr or "403" in stderr:
            return PublishResult(
                success=False,
                message_id=None,
                status_code=403,
                error_code="PERMISSION_DENIED",
                error_message=stderr,
                engine_used="gcloud-subprocess",
                latency_ms=latency,
            )
        else:
            return PublishResult(
                success=False,
                message_id=None,
                status_code=500,
                error_code="SUBPROCESS_FAILURE",
                error_message=stderr,
                engine_used="gcloud-subprocess",
                latency_ms=latency,
            )


def initialize_engine(engine_choice: str) -> Tuple[BasePublisherEngine, str]:
    """Detects and initializes the appropriate publisher engine."""
    if engine_choice in ("auto", "client"):
        try:
            engine = ClientLibraryEngine()
            return engine, "google-cloud-pubsub (Native Client Library)"
        except (ImportError, ModuleNotFoundError) as e:
            if engine_choice == "client":
                print(f"[FATAL] Client library forced but unavailable: {e}", file=sys.stderr)
                sys.exit(2)
            # Auto fallback to gcloud
            pass

    try:
        engine = SubprocessGcloudEngine()
        return engine, "gcloud-subprocess (CLI Fallback Engine)"
    except Exception as e:
        print(f"[FATAL] Unable to initialize any publisher engine: {e}", file=sys.stderr)
        sys.exit(2)


# ==============================================================================
# Payload Generators
# ==============================================================================

def generate_valid_trades(count: int, preset: str = "sgx") -> List[Dict[str, Any]]:
    """Generates conforming equity trade execution events.

    Supports both 'global' (US tech equities) and 'sgx' (Singapore Exchange counters).
    Guarantees:
    - Unique trade_id per transaction.
    - Valid ticker and realistic price.
    - Standard board lot volume.
    - Strict buyer_id != seller_id (complying with anti-wash trading rule).
    - ISO-8601 UTC timestamp.
    - Trade status is EXECUTED.
    """
    trades = []
    base_ts = int(time.time())
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if preset == "global":
        instruments = GLOBAL_INSTRUMENTS
        buyer_list = GLOBAL_BUYER_BROKERS
        seller_list = GLOBAL_SELLER_BROKERS
        id_prefix = "TR-GL"
    else:
        instruments = SGX_INSTRUMENTS
        buyer_list = SGX_BUYER_BROKERS
        seller_list = SGX_SELLER_BROKERS
        id_prefix = "TR-SGX"

    for i in range(count):
        inst = instruments[i % len(instruments)]
        # Add slight realistic price fluctuation (+/- 1.5%)
        price_jitter = round(random.uniform(-0.015, 0.015) * inst["base_price"], 2)
        exec_price = max(0.01, round(inst["base_price"] + price_jitter, 2))

        buyer = buyer_list[i % len(buyer_list)]
        seller = seller_list[(i + 1) % len(seller_list)]
        # Safeguard anti-wash trading rule
        if buyer == seller:
            seller = seller_list[(i + 2) % len(seller_list)]

        trades.append({
            "trade_id": f"{id_prefix}-{base_ts}-{i + 1:04d}",
            "instrument_code": inst["ticker"],
            "price": exec_price,
            "volume": LOT_SIZES[i % len(LOT_SIZES)],
            "buyer_id": buyer,
            "seller_id": seller,
            "trade_timestamp": now_iso,
            "trade_status": "EXECUTED",
        })
    return trades


def generate_schema_violations() -> List[Tuple[str, Dict[str, Any], str]]:
    """Generates deliberately invalid payloads targeting perimeter schema rejection.

    Returns: List of (violation_name, payload_dict, expected_error_substring).
    """
    valid_base = generate_valid_trades(1)[0]

    # Violation 1: Missing Required trade_id
    payload_missing_id = {k: v for k, v in valid_base.items() if k != "trade_id"}

    # Violation 2: Price String Type Mismatch
    payload_string_price = {**valid_base, "trade_id": "TR-CORRUPT-002", "price": "MARKET_CLOSE"}

    # Violation 3: Volume Float Type Mismatch
    payload_float_volume = {**valid_base, "trade_id": "TR-CORRUPT-003", "volume": 100.5}

    # Violation 4: Invalid Enum Status Value
    payload_bad_enum = {**valid_base, "trade_id": "TR-CORRUPT-004", "trade_status": "PENDING"}

    return [
        ("Missing Required trade_id", payload_missing_id, "Field was not found in JSON object: trade_id"),
        ("String Price Type Mismatch", payload_string_price, "expected number_float"),
        ("Float Volume Type Mismatch", payload_float_volume, "expected number_integer"),
        ("Invalid Enum Status ('PENDING')", payload_bad_enum, "Invalid enum index without default value: TradeStatus"),
    ]


def generate_dlq_trigger_payload(invalid_timestamp: str = "NOT_A_TIMESTAMP") -> Dict[str, Any]:
    """Generates payload that passes Avro schema but fails BigQuery TIMESTAMP ingestion.

    In Avro schema, trade_timestamp is typed as 'string'.
    In BigQuery DDL, trade_timestamp is typed as 'TIMESTAMP NOT NULL'.
    Passing an invalid timestamp string passes topic ingress but triggers BigQuery
    Storage Write API parse failure, routing to DLQ after 5 attempts.
    """
    valid_base = generate_valid_trades(1)[0]
    return {
        **valid_base,
        "trade_id": f"TR-DLQ-TRIGGER-{int(time.time())}",
        "trade_timestamp": invalid_timestamp,
    }


# ==============================================================================
# Operational Modes Execution
# ==============================================================================

def run_mode_valid(engine: BasePublisherEngine, project_id: str, topic: str, count: int, delay: float, verbose: bool, preset: str = "global") -> int:
    """Executes Mode 1: Conforming trade events publishing."""
    currency = "USD" if preset == "global" else "SGD"
    label = "Global Tech" if preset == "global" else "SGX"
    print(f"\n[MODE: VALID] Generating and streaming {count} conforming {label} equity trade events...")
    trades = generate_valid_trades(count, preset=preset)
    successful = 0

    for idx, trade in enumerate(trades, 1):
        result = engine.publish(project_id, topic, trade)
        if result.success:
            successful += 1
            print(f"  [{idx:02d}/{count}] [200 OK] Trade: {trade['trade_id']} | Ticker: {trade['instrument_code']:<7} | Price: {currency} {trade['price']:>6.2f} | MsgId: {result.message_id} ({result.latency_ms:.1f}ms)")
            if verbose:
                print(f"       Payload: {json.dumps(trade)}")
        else:
            print(f"  [{idx:02d}/{count}] [FAILED] Trade: {trade['trade_id']} | Error: {result.error_code} - {result.error_message}", file=sys.stderr)

        if delay > 0 and idx < count:
            time.sleep(delay)

    print(f"\n[RESULT] Published {successful}/{count} messages successfully.")
    if successful == count:
        print("[SUCCESS] All trade events accepted by Pub/Sub and queued for BigQuery Direct Ingestion.")
        return 0
    else:
        print(f"[ERROR] {count - successful} messages failed publication.", file=sys.stderr)
        return 1


def run_mode_invalid_schema(engine: BasePublisherEngine, project_id: str, topic: str, verbose: bool) -> int:
    """Executes Mode 2: Perimeter schema rejection verification."""
    print("\n[MODE: INVALID-SCHEMA] Deliberately injecting schema violations to test perimeter defense...")
    violations = generate_schema_violations()
    rejected_count = 0

    for idx, (name, payload, expected_err) in enumerate(violations, 1):
        print(f"\n  --- Test Case {idx}: {name} ---")
        if verbose:
            print(f"  Injected Payload: {json.dumps(payload)}")

        result = engine.publish(project_id, topic, payload)

        if not result.success and result.status_code == 400:
            rejected_count += 1
            print("  [PERIMETER DEFENSE ACTIVE] Synchronously rejected with INVALID_ARGUMENT (400) as expected!")
            print(f"  Error Telemetry: {result.error_message}")
        elif result.success:
            print("[CRITICAL ERROR] Corrupt payload was ACCEPTED by Pub/Sub topic! Perimeter gate breached!", file=sys.stderr)
            print(f"  Accepted Message ID: {result.message_id}", file=sys.stderr)
            return 1
        else:
            print(f"  [UNEXPECTED ERROR] Received status {result.status_code}: {result.error_message}", file=sys.stderr)
            return 1

    print(f"\n[RESULT] Successfully verified perimeter rejection on all {rejected_count}/{len(violations)} test cases.")
    print("[SUCCESS] Pub/Sub Schema Registry perimeter defense is active and enforcing contract boundaries.")
    return 0


def run_mode_trigger_dlq(engine: BasePublisherEngine, project_id: str, topic: str, wait_for_dlq: bool, dlq_sub: str, verbose: bool) -> int:
    """Executes Mode 3: Two-tier storage rejection & DLQ quarantine demonstration."""
    print("\n[MODE: TRIGGER-DLQ] Emitting payload with valid Avro string but malformed BigQuery TIMESTAMP...")
    payload = generate_dlq_trigger_payload(invalid_timestamp="NOT_A_TIMESTAMP")

    print(f"  Target Trade ID: {payload['trade_id']}")
    print(f"  Injected Timestamp: '{payload['trade_timestamp']}' (Conforms to Avro 'string', violates BQ 'TIMESTAMP')")
    if verbose:
        print(f"  Full Payload: {json.dumps(payload)}")

    result = engine.publish(project_id, topic, payload)

    if not result.success:
        print(f"  [ERROR] Ingress publish failed unexpectedly: {result.error_code} - {result.error_message}", file=sys.stderr)
        return 1

    print(f"  [STAGE 1: INGRESS SUCCESS] Broker accepted message with Message ID: {result.message_id}")
    print("  [STAGE 2: DOWNSTREAM FAILURE] BigQuery Direct Subscription will attempt Storage Write API insertion.")
    print("  [STAGE 3: RETRY LOOP] BigQuery will reject timestamp parsing; Pub/Sub service agent will retry up to 5 times.")
    print("  [STAGE 4: DLQ ROUTING] After retries exhaust (~45-60s), message will be quarantined into Dead-Letter Queue.")

    dlq_pull_cmd = f"gcloud pubsub subscriptions pull {dlq_sub} --auto-ack --limit=1 --format=json"
    print(f"\n  To inspect quarantined message in DLQ, run:\n    {dlq_pull_cmd}\n")

    if wait_for_dlq:
        print(f"  [POLLING] Waiting up to 90 seconds for DLQ arrival on subscription '{dlq_sub}'...")
        deadline = time.time() + 90.0
        gcloud_bin = shutil.which("gcloud") or "gcloud"
        found = False

        while time.time() < deadline:
            time.sleep(10)
            cmd = [gcloud_bin, "pubsub", "subscriptions", "pull", dlq_sub, "--auto-ack", "--limit=5", "--format=json"]
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if proc.returncode == 0 and proc.stdout.strip():
                try:
                    msgs = json.loads(proc.stdout.strip())
                    for m in msgs:
                        msg_payload = m.get("message", {})
                        attrs = msg_payload.get("attributes", {})
                        err_header = attrs.get("CloudPubSubDeadLetterSourceDeliveryErrorMessage", "")
                        if "trade_timestamp" in err_header or payload["trade_id"] in str(msg_payload):
                            print("\n  [DLQ CONFIRMED] Message received in Dead Letter Queue!")
                            print(f"  Diagnostic Attribute: CloudPubSubDeadLetterSourceDeliveryErrorMessage = '{err_header}'")
                            print(f"  Delivery Count: {attrs.get('CloudPubSubDeadLetterSourceDeliveryCount')}")
                            found = True
                            break
                    if found:
                        break
                except Exception:
                    pass
            print("    Still waiting for retry exhaustion and DLQ routing...")

        if not found:
            print("  [WARNING] DLQ polling timed out (message may still be in retry backoff).")
            print(f"  Run manually: {dlq_pull_cmd}")

    return 0


# ==============================================================================
# Main CLI Entry Point
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="SGX Equity Trade Event Producer & Data Contract Verification Script.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--project-id",
        default=None,
        help="Google Cloud Project ID (defaults to gcloud configured project or PROJECT_ID env var).",
    )
    parser.add_argument(
        "--topic",
        default="sgx-equity-trades-topic",
        help="Target Pub/Sub topic name or full resource path (default: 'sgx-equity-trades-topic').",
    )
    parser.add_argument(
        "--mode",
        choices=["valid", "invalid-schema", "trigger-dlq"],
        default="valid",
        help="Execution mode: 'valid' (stream conforming trades), 'invalid-schema' (test perimeter defense), 'trigger-dlq' (test DLQ routing).",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=10,
        help="Number of trade events to generate in 'valid' mode (default: 10, recommended: 10-20).",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.1,
        help="Delay in seconds between successive publishes in 'valid' mode (default: 0.1s).",
    )
    parser.add_argument(
        "--engine",
        choices=["auto", "client", "gcloud"],
        default="auto",
        help="Publisher engine: 'auto' (preferred client library, fallback gcloud), 'client' (force google-cloud-pubsub), 'gcloud' (force gcloud CLI).",
    )
    parser.add_argument(
        "--wait-for-dlq",
        action="store_true",
        help="In 'trigger-dlq' mode, poll the DLQ subscription for up to 90 seconds to verify message quarantine.",
    )
    parser.add_argument(
        "--dlq-sub",
        default="sgx-equity-trades-dlq-sub",
        help="DLQ subscription name for --wait-for-dlq verification (default: 'sgx-equity-trades-dlq-sub').",
    )
    parser.add_argument(
        "--preset",
        choices=["global", "sgx"],
        default="global",
        help="Market data preset: 'global' (US tech equities AAPL, GOOGL, MSFT, etc.) or 'sgx' (Singapore Exchange counters D05.SI, Z74.SI, etc.) [default: global].",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print verbose JSON payloads and telemetry.",
    )

    args = parser.parse_args()

    # Resolve Project ID
    project_id = args.project_id
    if not project_id:
        project_id = os.environ.get("PROJECT_ID")
    if not project_id:
        # Try gcloud config
        try:
            res = subprocess.run(
                ["gcloud", "config", "get-value", "project"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            if res.returncode == 0:
                lines = [l.strip() for l in res.stdout.strip().splitlines() if l.strip()]
                if lines and lines[-1] != "(unset)":
                    project_id = lines[-1]
        except Exception:
            pass

    if not project_id:
        print("[ERROR] Could not resolve Google Cloud Project ID. Provide --project-id or set PROJECT_ID environment variable.", file=sys.stderr)
        sys.exit(2)

    # Initialize Engine
    engine, engine_name = initialize_engine(args.engine)
    print("=" * 78)
    print("DATA CONTRACT TRADING EVENT PRODUCER & VALIDATOR")
    print(f"Project ID : {project_id}")
    print(f"Topic      : {args.topic}")
    print(f"Preset     : {args.preset.upper()}")
    print(f"Mode       : {args.mode}")
    print(f"Engine     : {engine_name}")
    print("=" * 78)

    # Route by Mode
    if args.mode == "valid":
        exit_code = run_mode_valid(
            engine=engine,
            project_id=project_id,
            topic=args.topic,
            count=args.count,
            delay=args.delay,
            verbose=args.verbose,
            preset=args.preset,
        )
    elif args.mode == "invalid-schema":
        exit_code = run_mode_invalid_schema(
            engine=engine,
            project_id=project_id,
            topic=args.topic,
            verbose=args.verbose,
        )
    elif args.mode == "trigger-dlq":
        exit_code = run_mode_trigger_dlq(
            engine=engine,
            project_id=project_id,
            topic=args.topic,
            wait_for_dlq=args.wait_for_dlq,
            dlq_sub=args.dlq_sub,
            verbose=args.verbose,
        )
    else:
        print(f"[FATAL] Unknown mode: {args.mode}", file=sys.stderr)
        exit_code = 2

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
