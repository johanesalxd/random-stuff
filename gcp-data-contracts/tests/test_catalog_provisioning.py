#!/usr/bin/env python3
"""Hermetic unit tests for Phase 1 Dataplex Catalog Provisioning & Curated View."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.dataplex_rest import (
    DataplexApiError,
    DataplexClient,
    HttpResponse,
    redact_headers,
)
from scripts.provision_catalog import (
    DEFINITION_LINK_TYPE,
    ENTRY_LINK_ID_REGEX,
    build_provisioning_plan,
    execute_apply,
    execute_teardown,
    extract_schema_properties,
    extract_target_coordinates,
    load_catalog_configs,
    render_curated_view_sql,
)


class FakeTransport:
    """In-memory fake HTTP transport for hermetic DataplexClient testing."""

    def __init__(self, responses: Optional[Dict[str, List[HttpResponse]]] = None) -> None:
        self.responses = responses or {}
        self.calls: List[Dict[str, Any]] = []

    def request(
        self,
        method: str,
        url: str,
        body: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> HttpResponse:
        self.calls.append(
            {"method": method, "url": url, "body": body, "headers": headers}
        )
        key = f"{method} {url}"
        if key in self.responses and self.responses[key]:
            return self.responses[key].pop(0)
        if method == "GET":
            if "/entries/" in url:
                return HttpResponse(status_code=200, body={"name": url})
            return HttpResponse(status_code=404, body={"error": {"message": "Not found"}})
        if method in ("POST", "PATCH", "DELETE"):
            return HttpResponse(status_code=200, body={"name": url, "done": True})
        return HttpResponse(status_code=200, body={})


class TestCatalogProvisioning(unittest.TestCase):
    """Tests for config loading, SQL rendering, REST plan building, and client execution."""

    @classmethod
    def setUpClass(cls) -> None:
        (
            cls.contract,
            cls.glossary_cfg,
            cls.product_cfg,
            cls.aspect_payload,
        ) = load_catalog_configs(REPO_ROOT)
        cls.dataset_id, cls.table_id, cls.location = extract_target_coordinates(
            cls.contract
        )

    def test_glossary_terms_match_contract_columns(self) -> None:
        """All 8 source terms in business_glossary.yaml map 1:1 to contract.odcs.yaml columns."""
        contract_cols = [
            str(p["name"]) for p in extract_schema_properties(self.contract)
        ]
        term_cols = [
            str(t["column_name"]) for t in self.glossary_cfg.get("terms", [])
        ]
        self.assertEqual(len(contract_cols), 8)
        self.assertEqual(term_cols, contract_cols)

    def test_curated_view_sql_drift_and_all_9_predicates(self) -> None:
        """Rendered curated view SQL matches sql/create_curated_view.sql and includes all 9 predicates."""
        rendered = render_curated_view_sql(self.contract, self.glossary_cfg)
        sql_file = REPO_ROOT / "sql" / "create_curated_view.sql"
        self.assertTrue(sql_file.exists(), "sql/create_curated_view.sql must exist")
        committed = sql_file.read_text(encoding="utf-8")
        self.assertEqual(rendered, committed)

        self.assertEqual(rendered.count("("), rendered.count(")"))
        self.assertEqual(
            rendered.count("[Inherited: Upstream Source Dictionary]"), 8
        )
        self.assertEqual(
            rendered.count(
                "[Platform-Derived: Steward Authored (AI-Assisted Pattern)]"
            ),
            2,
        )

        for predicate in (
            "trade_id IS NOT NULL",
            "instrument_code IS NOT NULL",
            "price IS NOT NULL",
            "price > 0",
            "volume IS NOT NULL",
            "volume > 0",
            "buyer_id != seller_id",
            "trade_status IN ('EXECUTED', 'CANCELLED', 'AMENDED')",
            "trade_timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 2 HOUR)",
            "ROUND(price * volume, 2) AS notional_value",
            "(buyer_id = seller_id) AS wash_trade_flag",
        ):
            self.assertIn(predicate, rendered)

        self.assertNotIn("QUALIFY ROW_NUMBER()", rendered)

    def test_build_provisioning_plan_completeness_and_iam_configs(self) -> None:
        """Plan includes 33 items, supports --bind-asset-iam accessGroupConfigs, and uses distinct group principals."""
        plan = build_provisioning_plan(
            project_id="test-proj",
            project_number="123456789012",
            location=self.location,
            dataset_id=self.dataset_id,
            table_id=self.table_id,
            glossary_cfg=self.glossary_cfg,
            product_cfg=self.product_cfg,
            aspect_payload=self.aspect_payload,
            owner_email="steward@example.com",
            bind_asset_iam=True,
        )
        self.assertEqual(len(plan), 33)

        by_cat: Dict[str, List[Any]] = {}
        for item in plan:
            by_cat.setdefault(item.category, []).append(item)

        self.assertEqual(len(by_cat["glossary"]), 1)
        self.assertEqual(len(by_cat["category"]), 3)
        self.assertEqual(len(by_cat["term"]), 8)
        self.assertEqual(len(by_cat["entry_link"]), 16)
        self.assertEqual(len(by_cat["data_product"]), 1)
        self.assertEqual(len(by_cat["data_asset"]), 2)
        self.assertEqual(len(by_cat["entry_aspect"]), 2)

        dp_req = by_cat["data_product"][0]
        self.assertIn("accessGroups", dp_req.update_mask or "")
        principals = [
            g["principal"]["googleGroup"]
            for g in dp_req.body["accessGroups"].values()
        ]
        self.assertEqual(len(principals), len(set(principals)))

        for asset_req in by_cat["data_asset"]:
            self.assertIn("accessGroupConfigs", asset_req.body)
            self.assertIn("accessGroupConfigs", asset_req.update_mask or "")

        seen_ids = set()
        for link_req in by_cat["entry_link"]:
            link_id = link_req.create_url.split("entryLinkId=")[-1]
            self.assertRegex(link_id, ENTRY_LINK_ID_REGEX)
            self.assertNotIn(link_id, seen_ids)
            seen_ids.add(link_id)
            self.assertEqual(link_req.body["entryLinkType"], DEFINITION_LINK_TYPE)

    def test_header_redaction_never_leaks_bearer_token(self) -> None:
        """redact_headers replaces Authorization bearer tokens with [REDACTED]."""
        raw = {
            "Authorization": "Bearer mock-bearer-credential-xyz",
            "x-goog-user-project": "test-proj",
        }
        redacted = redact_headers(raw)
        self.assertEqual(redacted["Authorization"], "Bearer [REDACTED]")
        self.assertNotIn("mock-bearer-credential-xyz", str(redacted))

    def test_execute_apply_and_teardown_hermetic(self) -> None:
        """execute_apply and execute_teardown converge and reverse-delete cleanly via FakeTransport."""
        fake = FakeTransport()
        client = DataplexClient(transport=fake, sleep_fn=lambda _: None)
        plan = build_provisioning_plan(
            project_id="test-proj",
            project_number="123456789012",
            location=self.location,
            dataset_id=self.dataset_id,
            table_id=self.table_id,
            glossary_cfg=self.glossary_cfg,
            product_cfg=self.product_cfg,
            aspect_payload=self.aspect_payload,
            owner_email="steward@example.com",
        )
        counts = execute_apply(
            client=client,
            plan=plan,
            project_id="test-proj",
            location=self.location,
            dataset_id=self.dataset_id,
            table_id=self.table_id,
        )
        self.assertEqual(counts["created_or_updated"], 33)

        td_counts = execute_teardown(client=client, plan=plan)
        self.assertEqual(td_counts["deleted"], 31)

    def test_permission_denied_raises_helpful_error(self) -> None:
        """HTTP 403 raises DataplexApiError containing IAM role remediation guidance."""
        url = "https://dataplex.googleapis.com/v1/projects/p/locations/l/glossaries"
        fake = FakeTransport(
            responses={
                f"GET {url}": [
                    HttpResponse(
                        status_code=403,
                        body={"error": {"message": "Permission denied"}},
                    )
                ]
            }
        )
        client = DataplexClient(transport=fake, sleep_fn=lambda _: None)
        with self.assertRaises(DataplexApiError) as ctx:
            client.get_or_none(url)
        self.assertIn("roles/dataplex.catalogEditor", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
