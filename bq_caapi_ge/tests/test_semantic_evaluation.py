"""Tests for the native ADK semantic evaluation assets and metrics."""

from decimal import Decimal
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
import yaml

pytest.importorskip("google.adk")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from google.adk.evaluation.eval_case import Invocation  # noqa: E402
from google.adk.evaluation.eval_case import InvocationEvent  # noqa: E402
from google.adk.evaluation.eval_case import InvocationEvents  # noqa: E402
from google.adk.evaluation.eval_config import EvalConfig  # noqa: E402
from google.adk.evaluation.eval_config import (  # noqa: E402
    get_eval_metrics_from_config,
)
from google.adk.evaluation.eval_metrics import BaseCriterion  # noqa: E402
from google.adk.evaluation.eval_metrics import EvalMetric  # noqa: E402
from google.adk.evaluation.eval_metrics import EvalStatus  # noqa: E402
from google.adk.evaluation.eval_set import EvalSet  # noqa: E402
from google.genai import types  # noqa: E402

from advanced.app.semantic_analytics.evals import metrics  # noqa: E402
from semantic.registry import load_contracts  # noqa: E402

_EVAL_DIR = PROJECT_ROOT / "advanced" / "app" / "semantic_analytics" / "evals"


def _invocation(
    question: str,
    *,
    selector_text: str | None = None,
    sql_text: str | None = None,
) -> Invocation:
    events = []
    if selector_text is not None:
        events.append(
            InvocationEvent(
                author="semantic_analytics.semantic_context_selector",
                content=types.Content(
                    role="model", parts=[types.Part.from_text(text=selector_text)]
                ),
            )
        )
    if sql_text is not None:
        events.append(
            InvocationEvent(
                author="semantic_analytics.semantic_sql_generator",
                content=types.Content(
                    role="model", parts=[types.Part.from_text(text=sql_text)]
                ),
            )
        )
    return Invocation(
        invocation_id=question,
        user_content=types.Content(
            role="user", parts=[types.Part.from_text(text=question)]
        ),
        intermediate_data=InvocationEvents(invocation_events=events),
    )


def _metric(name: str) -> EvalMetric:
    return EvalMetric(
        metric_name=name,
        criterion=BaseCriterion(threshold=1.0),
    )


class _FakeBigQueryClient:
    def __init__(
        self,
        sources: tuple[str, ...],
        rows: tuple[dict[str, object], ...] = (),
    ) -> None:
        self.calls: list[tuple[str, object, str]] = []
        self._sources = sources
        self._rows = rows

    def query(self, sql: str, *, job_config: object, location: str) -> object:
        self.calls.append((sql, job_config, location))
        if job_config.dry_run:
            return SimpleNamespace(
                statement_type="SELECT",
                referenced_tables=[
                    SimpleNamespace(
                        project=source.split(".")[0],
                        dataset_id=source.split(".")[1],
                        table_id=source.split(".")[2],
                    )
                    for source in self._sources
                ],
                total_bytes_processed=500,
            )
        return SimpleNamespace(result=lambda: self._rows)


def test_eval_assets_define_aligned_twelve_case_suite():
    """Tests EvalSet prompts and gold cases stay aligned and locally bounded."""
    eval_set = json.loads(
        (_EVAL_DIR / "thelook_narrow.evalset.json").read_text(encoding="utf-8")
    )
    gold = yaml.safe_load((_EVAL_DIR / "gold_cases.yaml").read_text(encoding="utf-8"))

    eval_cases = eval_set["eval_cases"]
    gold_cases = gold["cases"]
    parsed_eval_set = EvalSet.model_validate(eval_set)
    contracts = load_contracts(_EVAL_DIR / "contracts")
    eval_questions = {
        case["conversation"][0]["user_content"]["parts"][0]["text"]
        for case in eval_cases
    }
    gold_questions = {case["question"] for case in gold_cases}

    assert len(eval_cases) == 12
    assert len(gold_cases) == 12
    assert len(eval_questions) == 12
    assert len(gold_questions) == 12
    assert len(parsed_eval_set.eval_cases) == 12
    assert {contract.id for contract in contracts} == {
        "thelook_inventory",
        "thelook_orders",
    }
    assert {case["eval_id"] for case in eval_cases} == {
        case["id"] for case in gold_cases
    }
    assert eval_questions == gold_questions
    assert all(
        source.startswith("johanesa-playground-326616.thelook_ecommerce.")
        for case in gold_cases
        for source in case["expected_sources"]
    )


def test_eval_config_loads_custom_metric_functions():
    """Tests ADK resolves both custom metric functions from the config."""
    config = EvalConfig.model_validate_json(
        (_EVAL_DIR / "eval_config.json").read_text(encoding="utf-8")
    )

    configured_metrics = get_eval_metrics_from_config(config)

    assert {
        metric.metric_name: metric.custom_function_path for metric in configured_metrics
    } == {
        "semantic_selection_match": (
            "advanced.app.semantic_analytics.evals.metrics.semantic_selection_match"
        ),
        "bigquery_result_match": (
            "advanced.app.semantic_analytics.evals.metrics.bigquery_result_match"
        ),
    }
    assert all(metric.criterion.threshold == 1.0 for metric in configured_metrics)


def test_semantic_selection_match_accepts_oracle_selection():
    """Tests semantic selection passes when every oracle field matches."""
    selection = {
        "selected_contexts": [
            {
                "context_id": "thelook_orders",
                "context_version": 1,
                "metric_ids": ["completed_order_count"],
                "dimension_ids": [],
                "relationship_ids": [],
            }
        ],
        "requires_broad_catalog": False,
    }
    invocation = _invocation(
        "How many completed orders were placed?",
        selector_text=json.dumps(selection),
    )

    result = metrics.semantic_selection_match(
        _metric("semantic_selection_match"), [invocation], None, None
    )

    assert result.overall_score == 1.0
    assert result.overall_eval_status is EvalStatus.PASSED
    assert result.per_invocation_results[0].eval_status is EvalStatus.PASSED


def test_semantic_selection_match_rejects_extra_dimension():
    """Tests semantic selection fails when the selector adds a semantic ID."""
    selection = {
        "selected_contexts": [
            {
                "context_id": "thelook_orders",
                "context_version": 1,
                "metric_ids": ["completed_order_count"],
                "dimension_ids": ["country"],
                "relationship_ids": [],
            }
        ],
        "requires_broad_catalog": False,
    }
    invocation = _invocation(
        "How many completed orders were placed?",
        selector_text=json.dumps(selection),
    )

    result = metrics.semantic_selection_match(
        _metric("semantic_selection_match"), [invocation], None, None
    )

    assert result.overall_score == 0.0
    assert result.overall_eval_status is EvalStatus.FAILED


def test_rows_equal_ignores_order_and_allows_numeric_tolerance():
    """Tests result comparison handles unordered rows and numeric tolerance."""
    candidate = (("US", 4.0000001), ("DE", 3.0))
    gold = (("DE", 3.0), ("US", 4.0))

    assert metrics._rows_equal(
        candidate,
        gold,
        ordered=False,
        relative=1e-6,
        absolute=1e-9,
    )


def test_rows_equal_preserves_order_when_required():
    """Tests result comparison rejects reversed rows for ordered results."""
    assert not metrics._rows_equal(
        ((1,), (2,)),
        ((2,), (1,)),
        ordered=True,
        relative=1e-6,
        absolute=1e-9,
    )


def test_normalize_sql_removes_supported_code_fence():
    """Tests SQL extraction accepts the model's fenced SQL representation."""
    assert metrics._normalize_sql("```sql\nSELECT 1\n```") == "SELECT 1"


def test_execute_checked_query_runs_only_allowed_sources():
    """Tests an allowed SELECT executes with the configured billing cap."""
    source = "johanesa-playground-326616.thelook_ecommerce.orders"
    client = _FakeBigQueryClient((source,), ({"value": Decimal("3.25")},))

    rows = metrics._execute_checked_query(
        client,
        "SELECT 3.25",
        allowed_sources=frozenset({source}),
        maximum_bytes=1_000,
        location="US",
    )

    assert rows == ((3.25,),)
    assert len(client.calls) == 2
    assert client.calls[0][1].dry_run is True
    assert client.calls[1][1].maximum_bytes_billed == 1_000


def test_execute_checked_query_rejects_unexpected_source_before_execution():
    """Tests source mismatch stops after the dry run."""
    client = _FakeBigQueryClient(("other-project.dataset.orders",))

    with pytest.raises(ValueError, match="source mismatch"):
        metrics._execute_checked_query(
            client,
            "SELECT 1",
            allowed_sources=frozenset(
                {"johanesa-playground-326616.thelook_ecommerce.orders"}
            ),
            maximum_bytes=1_000,
            location="US",
        )

    assert len(client.calls) == 1
