#!/usr/bin/env python3
"""Unit and integration tests for Phase 2 Business Data Contract & Quality Grade Portal."""

from __future__ import annotations

import json
import sys
import threading
import urllib.error
import urllib.request
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.provision_catalog import load_catalog_configs, load_yaml_file
from scripts.run_contract_portal import (
    build_snapshot,
    compute_nutri_grade,
    create_http_handler,
    filter_curated_records,
    is_valid_loopback_host,
    render_portal_html,
    safe_json_for_html_script,
)
from scripts.run_dataplex_scan import OfflineSimulationEngine


class TestContractPortal(unittest.TestCase):
    """Tests for 9-rule A-E reachability, curated view evaluation, DNS rebinding guard, and static export."""

    @classmethod
    def setUpClass(cls) -> None:
        _, _, cls.product_cfg, _ = load_catalog_configs(REPO_ROOT)
        cls.thresholds = cls.product_cfg.get("nutri_grade_thresholds", {})
        cls.snapshot = build_snapshot(source="offline")

    def test_all_five_grades_reachable_on_9_rule_engine(self) -> None:
        """Every grade A, B, C, D, and E is reachable on the discrete 9-rule scorecard."""
        # 9/9 passed (100.00%, 0 critical) -> A
        self.assertEqual(
            compute_nutri_grade(round(100.0 * 9 / 9, 2), 0, self.thresholds)["grade"],
            "A",
        )
        # 8/9 passed (88.89%, 0 critical) -> B
        self.assertEqual(
            compute_nutri_grade(round(100.0 * 8 / 9, 2), 0, self.thresholds)["grade"],
            "B",
        )
        # 7/9 passed (77.78%, 1 critical) -> C
        self.assertEqual(
            compute_nutri_grade(round(100.0 * 7 / 9, 2), 1, self.thresholds)["grade"],
            "C",
        )
        # 6/9 passed (66.67%, 2 critical) -> D
        self.assertEqual(
            compute_nutri_grade(round(100.0 * 6 / 9, 2), 2, self.thresholds)["grade"],
            "D",
        )
        # 5/9 passed (55.56%, 3 critical) -> E
        self.assertEqual(
            compute_nutri_grade(round(100.0 * 5 / 9, 2), 3, self.thresholds)["grade"],
            "E",
        )

    def test_curated_filter_genuinely_evaluates_to_grade_a_9_of_9(self) -> None:
        """filter_curated_records filters 14 synthetic rows to 10 conforming rows and evaluates 9/9 PASS."""
        spec_path = REPO_ROOT / "config" / "dataplex_dq_spec.yaml"
        sim = OfflineSimulationEngine(
            project_id="demo-project",
            dataset_id="sgx_market_data",
            table_id="equity_trades",
            spec_file=spec_path,
        )
        dq_spec = load_yaml_file(spec_path)
        raw_records, _ = sim.generate_synthetic_dataset()
        self.assertEqual(len(raw_records), 14)

        curated_records = filter_curated_records(raw_records)
        self.assertEqual(len(curated_records), 10)
        curated_eval = sim.evaluate_rules(dq_spec, curated_records)
        self.assertEqual(sum(1 for r in curated_eval if r.passed), 9)

        curated_prof = self.snapshot["profiles"]["curated"]
        self.assertEqual(curated_prof["rows_evaluated"], 10)
        self.assertEqual(curated_prof["passed_rules"], 9)
        self.assertEqual(curated_prof["failed_rules"], 0)
        self.assertEqual(curated_prof["nutri_grade"]["grade"], "A")

        raw_prof = self.snapshot["profiles"]["raw"]
        self.assertEqual(raw_prof["rows_evaluated"], 14)
        self.assertEqual(raw_prof["passed_rules"], 5)
        self.assertEqual(raw_prof["failed_rules"], 4)
        self.assertEqual(raw_prof["nutri_grade"]["grade"], "E")

    def test_gate3_quarantine_samples_match_exact_anomaly_rows(self) -> None:
        """Gate 3 quarantine payload accurately binds TR-VIOL-PRICE-002 (price < 0) and TR-VIOL-WASH-004."""
        gate3 = self.snapshot["quarantine_samples"][2]
        payload = json.loads(gate3["payload_json"])
        neg = payload["negative_price_anomaly"]
        wash = payload["wash_trade_anomaly"]
        self.assertEqual(neg["trade_id"], "TR-VIOL-PRICE-002")
        self.assertLess(float(neg["price"]), 0.0)
        self.assertEqual(wash["trade_id"], "TR-VIOL-WASH-004")
        self.assertEqual(wash["buyer_id"], wash["seller_id"])

    def test_xss_script_escaping_and_committed_html_sync(self) -> None:
        """safe_json_for_html_script escapes <, >, & and portal/index.html is in sync."""
        malicious = {"payload": "</script><img src=x onerror=alert(1)>"}
        escaped = safe_json_for_html_script(malicious)
        self.assertNotIn("</script>", escaped)
        self.assertIn("\\u003c/script\\u003e", escaped)

        html_out = render_portal_html(self.snapshot)
        portal_file = REPO_ROOT / "portal" / "index.html"
        self.assertTrue(portal_file.exists())
        self.assertEqual(portal_file.read_text(encoding="utf-8"), html_out)

        self.assertNotIn("<script src=", html_out)
        self.assertNotIn('<link rel="stylesheet"', html_out)

    def test_local_http_server_routes_and_dns_rebinding_guards(self) -> None:
        """Local HTTP server serves /, /api/snapshot, enforces 403 on POST, and blocks prefix-bypass Host headers."""
        self.assertTrue(is_valid_loopback_host("127.0.0.1:8765"))
        self.assertTrue(is_valid_loopback_host("localhost:8765"))
        self.assertTrue(is_valid_loopback_host("[::1]:8765"))
        self.assertFalse(is_valid_loopback_host(""))
        self.assertFalse(is_valid_loopback_host("localhost.attacker.com:8765"))
        self.assertFalse(is_valid_loopback_host("127.0.0.1.nip.io:8765"))
        self.assertFalse(is_valid_loopback_host("localhostevil.com"))

        handler_cls = create_http_handler(
            self.snapshot, enable_access_requests=False
        )
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=5) as resp:
                self.assertEqual(resp.getcode(), 200)

            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/api/snapshot", timeout=5
            ) as resp:
                self.assertEqual(resp.getcode(), 200)
                data = json.loads(resp.read().decode("utf-8"))
                self.assertEqual(data["column_counts"]["all"], 10)

            for bad_host in (
                "evil.attacker.com",
                f"localhost.attacker.com:{port}",
                f"127.0.0.1.nip.io:{port}",
                "localhostevil.com",
            ):
                req_dns = urllib.request.Request(
                    f"http://127.0.0.1:{port}/api/snapshot",
                    headers={"Host": bad_host},
                )
                with self.assertRaises(urllib.error.HTTPError) as ctx_dns:
                    urllib.request.urlopen(req_dns, timeout=5)
                self.assertEqual(
                    ctx_dns.exception.code,
                    403,
                    f"Expected 403 for Host={bad_host}",
                )
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
