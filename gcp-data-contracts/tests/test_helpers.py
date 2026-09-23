"""Shared test helpers, oracles, probes, and fixtures for SGX Data Contracts test suite.

Provides authoritative oracles (gcloud pubsub schemas CLI wrapper), compiler runners,
fixture generators for SGX market data, and semantic validation helpers for BigQuery
and Dataplex Auto Data Quality specs.
"""

from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple, Union
import yaml

# Authoritative project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Reference Avro Schema matching Open Data Contract Standard (ODCS) specification
REFERENCE_AVRO_SCHEMA: Dict[str, Any] = {
    "type": "record",
    "name": "TradeEvent",
    "namespace": "com.sgx.equity",
    "doc": "SGX Real-Time Equity Trade Event Schema v1",
    "fields": [
        {"name": "trade_id", "type": "string", "doc": "Unique trade execution identifier"},
        {"name": "instrument_code", "type": "string", "doc": "SGX security ticker symbol (e.g. D05.SI, Z74.SI)"},
        {"name": "price", "type": "double", "doc": "Execution trade price in SGD"},
        {"name": "volume", "type": "long", "doc": "Number of shares executed"},
        {"name": "buyer_id", "type": "string", "doc": "Clearing participant ID of purchasing broker"},
        {"name": "seller_id", "type": "string", "doc": "Clearing participant ID of selling broker"},
        {"name": "trade_timestamp", "type": "string", "doc": "UTC execution timestamp (ISO-8601 format)"},
        {
            "name": "trade_status",
            "type": {
                "type": "enum",
                "name": "TradeStatus",
                "symbols": ["EXECUTED", "CANCELLED", "AMENDED"]
            },
            "doc": "Trade lifecycle state: EXECUTED, CANCELLED, AMENDED"
        }
    ]
}


class PubSubSchemaOracle:
    """Authoritative oracle leveraging Google Cloud SDK CLI for Pub/Sub schema validation."""

    @staticmethod
    def is_gcloud_available() -> bool:
        """Checks if gcloud CLI is available in PATH."""
        return shutil.which("gcloud") is not None

    @classmethod
    def validate_schema(
        cls,
        schema_def_or_path: Union[str, Path, Dict[str, Any]],
        schema_type: str = "AVRO"
    ) -> Tuple[int, str, str]:
        """Validates an Avro or Protobuf schema definition using gcloud.

        Returns: (exit_code, stdout, stderr)
        """
        if not cls.is_gcloud_available():
            raise RuntimeError("gcloud SDK is not installed or not available in PATH")

        if isinstance(schema_def_or_path, (dict, list)):
            def_str = json.dumps(schema_def_or_path)
            cmd = [
                "gcloud", "pubsub", "schemas", "validate-schema",
                f"--type={schema_type}",
                f"--definition={def_str}"
            ]
        elif isinstance(schema_def_or_path, Path) or (isinstance(schema_def_or_path, str) and Path(schema_def_or_path).is_file()):
            cmd = [
                "gcloud", "pubsub", "schemas", "validate-schema",
                f"--type={schema_type}",
                f"--definition-file={str(schema_def_or_path)}"
            ]
        else:
            cmd = [
                "gcloud", "pubsub", "schemas", "validate-schema",
                f"--type={schema_type}",
                f"--definition={str(schema_def_or_path)}"
            ]

        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()

    @classmethod
    def validate_message(
        cls,
        schema_def_or_path: Union[str, Path, Dict[str, Any]],
        message_json_or_dict: Union[str, Dict[str, Any]],
        schema_type: str = "AVRO",
        message_encoding: str = "JSON"
    ) -> Tuple[int, str, str]:
        """Validates a payload message against an Avro schema definition using gcloud.

        Returns: (exit_code, stdout, stderr)
        """
        if not cls.is_gcloud_available():
            raise RuntimeError("gcloud SDK is not installed or not available in PATH")

        msg_str = json.dumps(message_json_or_dict) if isinstance(message_json_or_dict, dict) else str(message_json_or_dict)

        if isinstance(schema_def_or_path, (dict, list)):
            def_str = json.dumps(schema_def_or_path)
            cmd = [
                "gcloud", "pubsub", "schemas", "validate-message",
                f"--type={schema_type}",
                f"--message-encoding={message_encoding}",
                f"--definition={def_str}",
                f"--message={msg_str}"
            ]
        elif isinstance(schema_def_or_path, Path) or (isinstance(schema_def_or_path, str) and Path(schema_def_or_path).is_file()):
            cmd = [
                "gcloud", "pubsub", "schemas", "validate-message",
                f"--type={schema_type}",
                f"--message-encoding={message_encoding}",
                f"--definition-file={str(schema_def_or_path)}",
                f"--message={msg_str}"
            ]
        else:
            cmd = [
                "gcloud", "pubsub", "schemas", "validate-message",
                f"--type={schema_type}",
                f"--message-encoding={message_encoding}",
                f"--definition={str(schema_def_or_path)}",
                f"--message={msg_str}"
            ]

        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


class CompilerRunner:
    """Invokes compile_contract.py via subprocess to evaluate opaque-box CLI behavior."""

    @staticmethod
    def compiler_path() -> Path:
        return PROJECT_ROOT / "compile_contract.py"

    @classmethod
    def exists(cls) -> bool:
        return cls.compiler_path().exists()

    @classmethod
    def run(
        cls,
        args: Optional[List[str]] = None,
        cwd: Optional[Path] = None,
        env: Optional[Dict[str, str]] = None
    ) -> subprocess.CompletedProcess:
        """Executes python3 compile_contract.py with given arguments."""
        script = str(cls.compiler_path())
        cmd = [sys.executable, script] + (args or [])
        work_dir = str(cwd or PROJECT_ROOT)
        return subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=work_dir,
            env=env,
            check=False
        )


class SGXTradeFixtures:
    """Deterministic fixtures for SGX trade execution events."""

    @staticmethod
    def now_iso() -> str:
        """Generates current UTC timestamp in ISO-8601 format."""
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    @classmethod
    def get_valid_trade_batch(cls, count: int = 10) -> List[Dict[str, Any]]:
        """Generates a batch of valid SGX equity trade execution events."""
        instruments = [
            ("D05.SI", 35.80, "BROKER_DBS_01", "BROKER_OCBC_02"),
            ("Z74.SI", 3.12, "BROKER_UOB_01", "BROKER_DBS_02"),
            ("O39.SI", 15.40, "BROKER_CITI_01", "BROKER_SCB_01"),
            ("U11.SI", 32.10, "BROKER_HSBC_01", "BROKER_MAYBANK_01"),
            ("F34.SI", 3.05, "BROKER_DBS_03", "BROKER_UOB_02"),
            ("C38U.SI", 1.95, "BROKER_OCBC_03", "BROKER_CITI_02"),
            ("BN4.SI", 7.85, "BROKER_SCB_02", "BROKER_HSBC_02"),
            ("BS6.SI", 1.15, "BROKER_MAYBANK_02", "BROKER_DBS_01"),
            ("A17U.SI", 2.80, "BROKER_UOB_03", "BROKER_OCBC_01"),
            ("G13.SI", 0.98, "BROKER_CITI_03", "BROKER_SCB_03"),
        ]
        batch: List[Dict[str, Any]] = []
        base_time = datetime.now(timezone.utc)

        for i in range(count):
            ticker, price, buyer, seller = instruments[i % len(instruments)]
            event_time = (base_time - timedelta(minutes=i * 2)).replace(microsecond=0).isoformat()
            batch.append({
                "trade_id": f"TR-SGX-20260914-{i+1:04d}",
                "instrument_code": ticker,
                "price": round(price + (i * 0.05), 2),
                "volume": 1000 * (i + 1),
                "buyer_id": buyer,
                "seller_id": seller,
                "trade_timestamp": event_time,
                "trade_status": "EXECUTED" if i != 4 else "AMENDED"
            })
        return batch

    @classmethod
    def get_invalid_ingress_payloads(cls) -> List[Tuple[str, Dict[str, Any], str]]:
        """Returns list of (test_case_name, invalid_payload, expected_error_substring)."""
        valid = cls.get_valid_trade_batch(1)[0]
        return [
            (
                "missing_trade_id",
                {k: v for k, v in valid.items() if k != "trade_id"},
                "Field was not found in JSON object: trade_id"
            ),
            (
                "missing_instrument_code",
                {k: v for k, v in valid.items() if k != "instrument_code"},
                "Field was not found in JSON object: instrument_code"
            ),
            (
                "string_price_type_mismatch",
                {**valid, "price": "expensive"},
                "expected number_float"
            ),
            (
                "string_volume_type_mismatch",
                {**valid, "volume": "high"},
                "expected number_integer"
            ),
            (
                "invalid_enum_symbol",
                {**valid, "trade_status": "PENDING"},
                "Invalid enum index without default value: TradeStatus"
            ),
            (
                "unsupported_enum_status",
                {**valid, "trade_status": "HALTED"},
                "Invalid enum index without default value: TradeStatus"
            )
        ]

    @classmethod
    def get_wash_trade_payload(cls) -> Dict[str, Any]:
        """Returns an equity trade event where buyer_id matches seller_id."""
        trade = cls.get_valid_trade_batch(1)[0]
        trade["trade_id"] = "TR-WASH-VIOLATION-001"
        trade["buyer_id"] = "BROKER_DBS_01"
        trade["seller_id"] = "BROKER_DBS_01"
        return trade

    @classmethod
    def get_stale_sla_payload(cls, hours_ago: float = 3.5) -> Dict[str, Any]:
        """Returns an equity trade event whose execution timestamp violates the 2h SLA."""
        trade = cls.get_valid_trade_batch(1)[0]
        trade["trade_id"] = "TR-SLA-VIOLATION-001"
        trade["trade_timestamp"] = (
            datetime.now(timezone.utc) - timedelta(hours=hours_ago)
        ).replace(microsecond=0).isoformat()
        return trade

    @classmethod
    def get_zero_negative_price_payloads(cls) -> List[Dict[str, Any]]:
        """Returns trade payloads with zero and negative prices."""
        valid = cls.get_valid_trade_batch(1)[0]
        return [
            {**valid, "trade_id": "TR-ZERO-PRICE-001", "price": 0.0},
            {**valid, "trade_id": "TR-NEG-PRICE-001", "price": -15.50},
        ]

    @classmethod
    def get_zero_negative_volume_payloads(cls) -> List[Dict[str, Any]]:
        """Returns trade payloads with zero and negative volumes."""
        valid = cls.get_valid_trade_batch(1)[0]
        return [
            {**valid, "trade_id": "TR-ZERO-VOL-001", "volume": 0},
            {**valid, "trade_id": "TR-NEG-VOL-001", "volume": -500},
        ]


class DataplexSpecEvaluator:
    """Evaluates semantic Dataplex quality expectations locally against trade events."""

    @staticmethod
    def evaluate_freshness(timestamp_str: str, max_age_hours: float = 2.0) -> bool:
        """Evaluates rowConditionExpectation: trade_timestamp >= CURRENT_TIMESTAMP - 2h."""
        try:
            # Handles ISO-8601 with trailing Z or +00:00
            clean_ts = timestamp_str.replace("Z", "+00:00")
            ts = datetime.fromisoformat(clean_ts)
            now = datetime.now(timezone.utc)
            return (now - ts) <= timedelta(hours=max_age_hours)
        except Exception:
            return False

    @staticmethod
    def evaluate_range(
        value: Union[int, float],
        min_value: Optional[float] = None,
        strict_min: bool = False,
        max_value: Optional[float] = None,
        strict_max: bool = False
    ) -> bool:
        """Evaluates Dataplex rangeExpectation."""
        if min_value is not None:
            if strict_min and value <= min_value:
                return False
            if not strict_min and value < min_value:
                return False
        if max_value is not None:
            if strict_max and value >= max_value:
                return False
            if not strict_max and value > max_value:
                return False
        return True

    @staticmethod
    def evaluate_anti_wash_trading(buyer_id: str, seller_id: str) -> bool:
        """Evaluates anti-wash trading rule: buyer_id != seller_id."""
        return buyer_id.strip() != seller_id.strip()

    @staticmethod
    def evaluate_trade_status_set(status: str) -> bool:
        """Evaluates trade_status setExpectation."""
        return status in {"EXECUTED", "CANCELLED", "AMENDED"}
