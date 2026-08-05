"""Custom ADK metrics for semantic selection and BigQuery result accuracy."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, time
from decimal import Decimal
import json
import logging
import math
import os
from pathlib import Path
import statistics
from typing import Any

from google.adk.evaluation.eval_case import ConversationScenario
from google.adk.evaluation.eval_case import Invocation
from google.adk.evaluation.eval_case import InvocationEvents
from google.adk.evaluation.eval_metrics import EvalMetric
from google.adk.evaluation.eval_metrics import EvalStatus
from google.adk.evaluation.evaluator import EvaluationResult
from google.adk.evaluation.evaluator import PerInvocationResult
from google.cloud import bigquery
import yaml

logger = logging.getLogger(__name__)

_FIXTURE_PATH = Path(__file__).with_name("gold_cases.yaml")
_SELECTOR_AUTHOR = "semantic_context_selector"
_SQL_AUTHOR = "semantic_sql_generator"
_DEFAULT_PROJECT = "johanesa-playground-326616"
_DEFAULT_LOCATION = "US"
_DEFAULT_MAXIMUM_BYTES = 1_000_000_000
_MAX_RESULT_ROWS = 100


def semantic_selection_match(
    eval_metric: EvalMetric,
    actual_invocations: list[Invocation],
    expected_invocations: list[Invocation] | None,
    conversation_scenario: ConversationScenario | None,
) -> EvaluationResult:
    """Checks structured selector output against the case's oracle selection."""
    del conversation_scenario

    def score(actual: Invocation) -> float:
        case = _case_for_invocation(actual)
        text = _event_text(actual, _SELECTOR_AUTHOR)
        if not text:
            logger.error("No selector event found for question: %s", _question(actual))
            return 0.0
        try:
            selected = json.loads(text)
        except json.JSONDecodeError:
            logger.error("Selector returned invalid JSON for case %s", case["id"])
            return 0.0
        actual_selection = _normalize_selection(selected.get("selected_contexts", []))
        expected_selection = _normalize_selection([case["selection"]])
        matched = (
            actual_selection == expected_selection
            and selected.get("requires_broad_catalog") is False
        )
        if not matched:
            logger.error(
                "Selection mismatch for %s: expected=%s actual=%s",
                case["id"],
                expected_selection,
                actual_selection,
            )
        return 1.0 if matched else 0.0

    return _evaluate_metric(
        eval_metric,
        actual_invocations,
        expected_invocations,
        score,
    )


def bigquery_result_match(
    eval_metric: EvalMetric,
    actual_invocations: list[Invocation],
    expected_invocations: list[Invocation] | None,
    conversation_scenario: ConversationScenario | None,
) -> EvaluationResult:
    """Compares generated-query results with the case's gold BigQuery result."""
    del conversation_scenario
    project = os.getenv("GOOGLE_CLOUD_PROJECT", _DEFAULT_PROJECT)
    location = os.getenv("BIGQUERY_LOCATION", _DEFAULT_LOCATION)
    maximum_bytes = _positive_int_env(
        "EVAL_MAXIMUM_BYTES_BILLED", _DEFAULT_MAXIMUM_BYTES
    )
    client = bigquery.Client(project=project, location=location)

    def score(actual: Invocation) -> float:
        case = _case_for_invocation(actual)
        candidate_sql = _event_text(actual, _SQL_AUTHOR)
        if not candidate_sql:
            logger.error("No SQL generator event found for case %s", case["id"])
            return 0.0
        candidate_sql = _normalize_sql(candidate_sql)
        allowed_sources = frozenset(case["expected_sources"])
        try:
            candidate_rows = _execute_checked_query(
                client,
                candidate_sql,
                allowed_sources=allowed_sources,
                maximum_bytes=maximum_bytes,
                location=location,
            )
            gold_rows = _execute_checked_query(
                client,
                case["gold_sql"],
                allowed_sources=allowed_sources,
                maximum_bytes=maximum_bytes,
                location=location,
            )
        except Exception as error:  # provider and generated-SQL boundary
            logger.error("BigQuery metric failed for %s: %s", case["id"], error)
            return 0.0
        matched = _rows_equal(
            candidate_rows,
            gold_rows,
            ordered=bool(case.get("ordered", False)),
            relative=float(case.get("float_relative_tolerance", 1e-6)),
            absolute=float(case.get("float_absolute_tolerance", 1e-9)),
        )
        if not matched:
            logger.error(
                "Result mismatch for %s: candidate=%s gold=%s sql=%s",
                case["id"],
                candidate_rows,
                gold_rows,
                candidate_sql,
            )
        return 1.0 if matched else 0.0

    return _evaluate_metric(
        eval_metric,
        actual_invocations,
        expected_invocations,
        score,
    )


def _evaluate_metric(
    eval_metric: EvalMetric,
    actual_invocations: list[Invocation],
    expected_invocations: list[Invocation] | None,
    scorer: Callable[[Invocation], float],
) -> EvaluationResult:
    per_invocation = []
    scores = []
    for index, actual in enumerate(actual_invocations):
        expected = (
            expected_invocations[index]
            if expected_invocations and index < len(expected_invocations)
            else None
        )
        try:
            score = scorer(actual)
        except (KeyError, ValueError) as error:
            logger.error("Metric fixture error: %s", error)
            score = 0.0
        scores.append(score)
        per_invocation.append(
            PerInvocationResult(
                actual_invocation=actual,
                expected_invocation=expected,
                score=score,
                eval_status=(
                    EvalStatus.PASSED
                    if score >= _threshold(eval_metric)
                    else EvalStatus.FAILED
                ),
            )
        )
    overall = statistics.mean(scores) if scores else 0.0
    return EvaluationResult(
        overall_score=overall,
        overall_eval_status=(
            EvalStatus.PASSED
            if overall >= _threshold(eval_metric)
            else EvalStatus.FAILED
        ),
        per_invocation_results=per_invocation,
    )


def _case_for_invocation(invocation: Invocation) -> dict[str, Any]:
    question = _question(invocation)
    case = _gold_cases().get(question)
    if case is None:
        raise KeyError(f"no gold case for question: {question!r}")
    return case


def _question(invocation: Invocation) -> str:
    return "".join(
        part.text or "" for part in invocation.user_content.parts or []
    ).strip()


def _event_text(invocation: Invocation, author: str) -> str:
    intermediate = invocation.intermediate_data
    if not isinstance(intermediate, InvocationEvents):
        return ""
    matches = []
    for event in intermediate.invocation_events:
        if not event.author.endswith(author) or not event.content:
            continue
        text = "".join(
            part.text or "" for part in event.content.parts or [] if not part.thought
        ).strip()
        if text:
            matches.append(text)
    return matches[-1] if matches else ""


def _normalize_selection(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = []
    for selection in raw:
        normalized.append(
            {
                "context_id": selection.get("context_id"),
                "context_version": selection.get("context_version"),
                "metric_ids": sorted(selection.get("metric_ids", [])),
                "dimension_ids": sorted(selection.get("dimension_ids", [])),
                "relationship_ids": sorted(selection.get("relationship_ids", [])),
            }
        )
    return sorted(normalized, key=lambda value: str(value["context_id"]))


def _execute_checked_query(
    client: bigquery.Client,
    sql: str,
    *,
    allowed_sources: frozenset[str],
    maximum_bytes: int,
    location: str,
) -> tuple[tuple[Any, ...], ...]:
    dry_job = client.query(
        sql,
        job_config=bigquery.QueryJobConfig(dry_run=True, use_query_cache=False),
        location=location,
    )
    statement_type = str(dry_job.statement_type or "").upper()
    if statement_type != "SELECT":
        raise ValueError(f"only SELECT is allowed, got {statement_type or 'UNKNOWN'}")
    referenced_sources = frozenset(
        f"{table.project}.{table.dataset_id}.{table.table_id}"
        for table in dry_job.referenced_tables or ()
    )
    if referenced_sources != allowed_sources:
        raise ValueError(
            f"source mismatch: expected {sorted(allowed_sources)}, "
            f"got {sorted(referenced_sources)}"
        )
    bytes_processed = int(dry_job.total_bytes_processed or 0)
    if bytes_processed > maximum_bytes:
        raise ValueError(
            f"query processes {bytes_processed} bytes, above {maximum_bytes}"
        )
    query_job = client.query(
        sql,
        job_config=bigquery.QueryJobConfig(
            maximum_bytes_billed=maximum_bytes,
            use_query_cache=True,
            labels={"semantic-eval-metric": "true"},
        ),
        location=location,
    )
    rows = []
    for index, row in enumerate(query_job.result()):
        if index >= _MAX_RESULT_ROWS:
            raise ValueError(f"query exceeded {_MAX_RESULT_ROWS} evaluation rows")
        rows.append(tuple(_normalize_value(value) for value in row.values()))
    return tuple(rows)


def _rows_equal(
    left: tuple[tuple[Any, ...], ...],
    right: tuple[tuple[Any, ...], ...],
    *,
    ordered: bool,
    relative: float,
    absolute: float,
) -> bool:
    if not ordered:
        left = tuple(sorted(left, key=_row_sort_key))
        right = tuple(sorted(right, key=_row_sort_key))
    if len(left) != len(right):
        return False
    return all(
        len(left_row) == len(right_row)
        and all(
            _values_equal(a, b, relative=relative, absolute=absolute)
            for a, b in zip(left_row, right_row)
        )
        for left_row, right_row in zip(left, right)
    )


def _values_equal(left: Any, right: Any, *, relative: float, absolute: float) -> bool:
    if (
        isinstance(left, (int, float))
        and not isinstance(left, bool)
        and isinstance(right, (int, float))
        and not isinstance(right, bool)
    ):
        return math.isclose(left, right, rel_tol=relative, abs_tol=absolute)
    return left == right


def _normalize_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.hex()
    return value


def _row_sort_key(row: tuple[Any, ...]) -> str:
    return json.dumps(row, ensure_ascii=False, default=str, separators=(",", ":"))


def _normalize_sql(value: str) -> str:
    text = value.strip()
    if not text.startswith("```") or not text.endswith("```"):
        return text
    lines = text.splitlines()
    if len(lines) >= 3 and lines[0].strip().lower() in {
        "```",
        "```sql",
        "```bigquery",
    }:
        return "\n".join(lines[1:-1]).strip()
    return text


def _threshold(eval_metric: EvalMetric) -> float:
    criterion = eval_metric.criterion
    if criterion is not None:
        return float(criterion.threshold)
    if eval_metric.threshold is not None:
        return float(eval_metric.threshold)
    return 1.0


def _positive_int_env(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _gold_cases() -> dict[str, dict[str, Any]]:
    raw = yaml.safe_load(_FIXTURE_PATH.read_text(encoding="utf-8"))
    cases = raw.get("cases", []) if isinstance(raw, dict) else []
    result = {}
    for case in cases:
        question = str(case.get("question", "")).strip()
        if question:
            result[question] = case
    return result
