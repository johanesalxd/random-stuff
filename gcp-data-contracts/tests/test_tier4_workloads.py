"""Tier 4: Realistic SGX Workload Simulations Test Suite.

Simulates production financial workloads on the Singapore Exchange (SGX):
1. Happy path streaming batch: 10 conforming SGX equity trade executions
2. Edge boundary ingress rejection: Synchronous wire gate rejection of malformed trades
3. Freshness SLA violation detection: Identification of delayed trade arrivals exceeding 2h SLA
4. Regulatory anti-wash trading detection: Identification of self-trading brokers
5. Financial price/volume anomaly detection: Negative or zero prices/volumes
6. Complete trade lifecycle state machine: EXECUTED -> AMENDED -> CANCELLED
"""

from datetime import datetime, timezone, timedelta
from pathlib import Path
import unittest

from tests.test_helpers import (
    PROJECT_ROOT,
    REFERENCE_AVRO_SCHEMA,
    DataplexSpecEvaluator,
    PubSubSchemaOracle,
    SGXTradeFixtures,
)


class TestTier4SGXWorkloads(unittest.TestCase):
    """Tier 4: End-to-end realistic financial workload simulations."""

    def setUp(self):
        compiled_avro = PROJECT_ROOT / "schemas" / "trade_event_v1.avsc"
        self.schema_source = compiled_avro if compiled_avro.exists() else REFERENCE_AVRO_SCHEMA

    def test_4_1_stream_batch_happy_path(self):
        """Simulation 1: Normal trading day stream batch (10 conforming SGX equity trades)."""
        if not PubSubSchemaOracle.is_gcloud_available():
            self.skipTest("gcloud SDK not available")

        trades = SGXTradeFixtures.get_valid_trade_batch(count=10)
        self.assertEqual(len(trades), 10)

        # 1. Wire Gate Validation (Pub/Sub Schema Registry)
        for trade in trades:
            with self.subTest(trade_id=trade["trade_id"], ticker=trade["instrument_code"]):
                exit_code, stdout, stderr = PubSubSchemaOracle.validate_message(
                    self.schema_source, trade, schema_type="AVRO", message_encoding="JSON"
                )
                output = f"{stdout}\n{stderr}"
                self.assertEqual(
                    exit_code, 0,
                    f"Conforming trade {trade['trade_id']} failed schema validation!\nOutput: {output}"
                )
                self.assertIn("Message is valid", output)

                # 2. Dataplex Quality Gate Validation
                # Non-null completeness
                for col in ["trade_id", "instrument_code", "price", "volume", "buyer_id", "seller_id"]:
                    self.assertIsNotNone(trade[col])

                # Range check: price > 0, volume > 0
                self.assertTrue(
                    DataplexSpecEvaluator.evaluate_range(trade["price"], min_value=0.0, strict_min=True),
                    f"Price {trade['price']} must be strictly > 0"
                )
                self.assertTrue(
                    DataplexSpecEvaluator.evaluate_range(trade["volume"], min_value=0, strict_min=True),
                    f"Volume {trade['volume']} must be strictly > 0"
                )

                # Anti-wash trading: buyer != seller
                self.assertTrue(
                    DataplexSpecEvaluator.evaluate_anti_wash_trading(trade["buyer_id"], trade["seller_id"]),
                    f"Counterparties must differ: {trade['buyer_id']} vs {trade['seller_id']}"
                )

                # Freshness SLA: trade_timestamp within 2 hours
                self.assertTrue(
                    DataplexSpecEvaluator.evaluate_freshness(trade["trade_timestamp"], max_age_hours=2.0),
                    f"Trade timestamp {trade['trade_timestamp']} must be within 2 hours"
                )

    def test_4_2_ingress_rejection_boundary(self):
        """Simulation 2: Edge boundary rejection gate (malformed payloads rejected at ingress)."""
        if not PubSubSchemaOracle.is_gcloud_available():
            self.skipTest("gcloud SDK not available")

        corrupt_events = [
            ("missing_trade_id", {"instrument_code": "D05.SI", "price": 35.80, "volume": 1000}),
            ("string_price", {"trade_id": "TR-001", "instrument_code": "D05.SI", "price": "MARKET_CLOSE", "volume": 1000, "buyer_id": "B1", "seller_id": "S1", "trade_timestamp": "2026-09-14T02:00:00Z", "trade_status": "EXECUTED"}),
            ("invalid_status", {"trade_id": "TR-002", "instrument_code": "D05.SI", "price": 35.80, "volume": 1000, "buyer_id": "B1", "seller_id": "S1", "trade_timestamp": "2026-09-14T02:00:00Z", "trade_status": "HALTED"}),
            ("float_volume", {"trade_id": "TR-003", "instrument_code": "D05.SI", "price": 35.80, "volume": 100.5, "buyer_id": "B1", "seller_id": "S1", "trade_timestamp": "2026-09-14T02:00:00Z", "trade_status": "EXECUTED"}),
        ]

        for name, corrupt_msg in corrupt_events:
            with self.subTest(scenario=name):
                exit_code, stdout, stderr = PubSubSchemaOracle.validate_message(
                    self.schema_source, corrupt_msg, schema_type="AVRO", message_encoding="JSON"
                )
                self.assertEqual(
                    exit_code, 1,
                    f"Corrupt event '{name}' was not rejected at the schema ingress gate!"
                )
                self.assertIn("INVALID_ARGUMENT", stderr)

    def test_4_3_freshness_sla_violation_detection(self):
        """Simulation 3: Freshness SLA violation detection (delayed trades flagged by Dataplex)."""
        if not PubSubSchemaOracle.is_gcloud_available():
            self.skipTest("gcloud SDK not available")

        now = datetime.now(timezone.utc)
        delayed_trades = [
            ("lag_2h15m", (now - timedelta(hours=2, minutes=15)).replace(microsecond=0).isoformat()),
            ("lag_4h00m", (now - timedelta(hours=4)).replace(microsecond=0).isoformat()),
            ("lag_24h00m", (now - timedelta(hours=24)).replace(microsecond=0).isoformat()),
        ]

        base_trade = SGXTradeFixtures.get_valid_trade_batch(1)[0]

        for label, delayed_ts in delayed_trades:
            with self.subTest(label=label):
                trade = {**base_trade, "trade_id": f"TR-SLA-{label}", "trade_timestamp": delayed_ts}

                # Step A: Syntactically valid ISO-8601 string passes wire gate
                exit_code, stdout, stderr = PubSubSchemaOracle.validate_message(
                    self.schema_source, trade, schema_type="AVRO", message_encoding="JSON"
                )
                self.assertEqual(exit_code, 0, "Wire gate expects valid string for ISO-8601 timestamp")

                # Step B: Dataplex Freshness Rule detects the SLA latency violation
                is_fresh = DataplexSpecEvaluator.evaluate_freshness(trade["trade_timestamp"], max_age_hours=2.0)
                self.assertFalse(
                    is_fresh,
                    f"Dataplex freshness rule failed to flag SLA violation for {label} ({delayed_ts})"
                )

    def test_4_4_anti_wash_trading_regulatory_surveillance(self):
        """Simulation 4: Regulatory surveillance detecting self-trading / wash trades."""
        if not PubSubSchemaOracle.is_gcloud_available():
            self.skipTest("gcloud SDK not available")

        wash_trade = SGXTradeFixtures.get_wash_trade_payload()

        # Step A: Wire schema accepts the payload (valid strings)
        exit_code, stdout, stderr = PubSubSchemaOracle.validate_message(
            self.schema_source, wash_trade, schema_type="AVRO", message_encoding="JSON"
        )
        self.assertEqual(exit_code, 0, "Wire gate accepts valid strings")

        # Step B: Dataplex Anti-Wash Trading assertion identifies the violation
        is_compliant = DataplexSpecEvaluator.evaluate_anti_wash_trading(
            wash_trade["buyer_id"], wash_trade["seller_id"]
        )
        self.assertFalse(
            is_compliant,
            f"Dataplex integrity assertion failed to catch wash trade: {wash_trade['buyer_id']} == {wash_trade['seller_id']}"
        )

    def test_4_5_financial_price_volume_outliers(self):
        """Simulation 5: Erroneous trade prices and volumes flagged by Dataplex range rules."""
        outlier_trades = [
            ("negative_price", -12.50, 1000),
            ("zero_price", 0.00, 1000),
            ("zero_volume", 35.80, 0),
            ("negative_volume", 35.80, -500),
        ]
        base_trade = SGXTradeFixtures.get_valid_trade_batch(1)[0]

        for label, test_price, test_vol in outlier_trades:
            with self.subTest(scenario=label):
                trade = {
                    **base_trade,
                    "trade_id": f"TR-OUTLIER-{label}",
                    "price": test_price,
                    "volume": test_vol
                }

                # Wire schema accepts double and long numbers
                if PubSubSchemaOracle.is_gcloud_available():
                    exit_code, stdout, stderr = PubSubSchemaOracle.validate_message(
                        self.schema_source, trade, schema_type="AVRO", message_encoding="JSON"
                    )
                    self.assertEqual(exit_code, 0, "Wire schema accepts signed numbers")

                # Dataplex range checks flag zero and negative boundaries
                price_valid = DataplexSpecEvaluator.evaluate_range(trade["price"], min_value=0.0, strict_min=True)
                vol_valid = DataplexSpecEvaluator.evaluate_range(trade["volume"], min_value=0, strict_min=True)

                self.assertFalse(
                    price_valid and vol_valid,
                    f"Dataplex range rules failed to flag outlier scenario: price={test_price}, volume={test_vol}"
                )

    def test_4_6_complete_trade_lifecycle_sequence(self):
        """Simulation 6: Complete trade lifecycle state transitions (EXECUTED -> AMENDED -> CANCELLED)."""
        if not PubSubSchemaOracle.is_gcloud_available():
            self.skipTest("gcloud SDK not available")

        trade_id = "TR-SGX-LIFECYCLE-001"
        base_time = datetime.now(timezone.utc) - timedelta(minutes=15)

        lifecycle_events = [
            ("EXECUTED", 35.80, 5000, base_time),
            ("AMENDED", 35.85, 5000, base_time + timedelta(minutes=5)),
            ("CANCELLED", 35.85, 0, base_time + timedelta(minutes=10)),
        ]

        for status, price, volume, event_time in lifecycle_events:
            with self.subTest(stage=status):
                event_payload = {
                    "trade_id": trade_id,
                    "instrument_code": "D05.SI",
                    "price": price,
                    "volume": 1000 if status == "CANCELLED" else volume,  # Wire volume positive
                    "buyer_id": "BROKER_DBS_01",
                    "seller_id": "BROKER_OCBC_02",
                    "trade_timestamp": event_time.replace(microsecond=0).isoformat(),
                    "trade_status": status
                }

                exit_code, stdout, stderr = PubSubSchemaOracle.validate_message(
                    self.schema_source, event_payload, schema_type="AVRO", message_encoding="JSON"
                )
                output = f"{stdout}\n{stderr}"
                self.assertEqual(
                    exit_code, 0,
                    f"Lifecycle state '{status}' failed schema validation!\nOutput: {output}"
                )
                self.assertIn("Message is valid", output)
                self.assertTrue(
                    DataplexSpecEvaluator.evaluate_trade_status_set(status),
                    f"Trade status '{status}' not in allowed set"
                )


if __name__ == "__main__":
    unittest.main()
