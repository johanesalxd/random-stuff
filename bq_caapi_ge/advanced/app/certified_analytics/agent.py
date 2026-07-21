"""ADK 2 workflow for local certified analytics."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Any

from google.adk.events.event import Event
from google.adk.workflow import Workflow

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from semantic.compiler import compile_query  # noqa: E402
from semantic.executor import (  # noqa: E402
    ExecutionError,
    execute_adc_developer_query,
    execute_adk_bigquery_adc_query,
)
from semantic.grounding import (  # noqa: E402
    GroundingError,
    disabled_grounding,
    load_adk_bigquery_catalog_adc,
)
from semantic.registry import load_contract  # noqa: E402
from semantic.types import CompileError, QueryIntent  # noqa: E402

_CONTRACT = load_contract()
_DISABLED = "disabled"
_COMPILE_ONLY = "compile_only"
_ADK_BIGQUERY_ADC = "adk_bigquery_adc"
_ADC_DEVELOPER = "adc_developer"
_DIMENSION_NAMES = {
    "country": "country",
    "geography": "country",
    "market": "country",
    "status": "order_status",
    "customer": "user_id",
    "customers": "user_id",
    "user": "user_id",
    "users": "user_id",
}
_COMPLETED_ORDERS_PATTERN = re.compile(
    r"(?:completed|complete|finished) orders?"
    r"(?: by (?P<dimension>country|geography|market|status|user|users|customer|customers))?"
)
_REVENUE_PATTERN = re.compile(
    r"(?:completed )?(?:revenue|sales)"
    r"(?: by (?P<dimension>country|geography|market|user|users|customer|customers))?"
)
_AOV_PATTERN = re.compile(
    r"(?:average order value|aov)"
    r"(?: by (?P<dimension>country|geography|market))?"
)
_TOP_USERS_PATTERN = re.compile(
    r"(?:top|best)(?: (?P<limit>\d+))? "
    r"(?P<entity>users?|customers?|spenders?) by "
    r"(?:completed revenue|total spend|revenue|sales|spend)"
)


def _extract_text(node_input: Any) -> str:
    if isinstance(node_input, str):
        return node_input.strip()

    parts = getattr(node_input, "parts", None)
    if parts:
        text_parts = [getattr(part, "text", "") for part in parts]
        return " ".join(part for part in text_parts if part).strip()

    return str(node_input).strip()


def _normalize_question(node_input: Any) -> dict[str, str]:
    question = _extract_text(node_input)
    return {"question": question, "normalized_question": question.lower()}


def _load_catalog_metadata(node_input: dict[str, str]) -> dict[str, Any]:
    grounding_mode = _grounding_mode()
    if grounding_mode == _DISABLED:
        grounding = disabled_grounding()
    elif grounding_mode == _ADK_BIGQUERY_ADC:
        try:
            grounding = load_adk_bigquery_catalog_adc(
                question=node_input["question"],
                project=os.getenv("GOOGLE_CLOUD_PROJECT"),
                location=os.getenv("DATAPLEX_LOCATION")
                or os.getenv("BIGQUERY_LOCATION"),
                dataset_id=os.getenv("BIGQUERY_DATASET_ID") or _CONTRACT.dataset,
                page_size=_grounding_page_size(),
            )
        except GroundingError as error:
            return {
                **node_input,
                "grounding": {
                    "status": "error",
                    "mode": grounding_mode,
                    "assets": [],
                    "error": str(error),
                },
            }
    else:
        return {
            **node_input,
            "grounding": {
                "status": "error",
                "mode": grounding_mode,
                "assets": [],
                "error": f"unsupported semantic grounding mode: {grounding_mode}",
            },
        }

    return {
        **node_input,
        "grounding": {
            "status": grounding.status,
            "mode": grounding.mode,
            "assets": list(grounding.assets),
            "error": grounding.error,
        },
    }


def _select_contract_intent(node_input: dict[str, Any]) -> Event:
    intent = _select_prototype_intent(node_input["normalized_question"])
    if intent is None:
        return Event(
            output={
                **node_input,
                "coverage_status": "unsupported_question_constraints",
                "reason": (
                    "The prototype selector only accepts a small set of complete "
                    "question shapes and cannot safely preserve this request."
                ),
            },
            route="refuse",
        )

    output = {
        **node_input,
        "intent": intent,
    }
    return Event(output=output, route="covered")


def _select_prototype_intent(normalized_question: str) -> QueryIntent | None:
    question = " ".join(normalized_question.strip(" ?!.").split())
    patterns = (
        (_COMPLETED_ORDERS_PATTERN, "completed_order_count"),
        (_REVENUE_PATTERN, "completed_revenue"),
        (_AOV_PATTERN, "average_order_value"),
    )
    for pattern, metric_name in patterns:
        match = pattern.fullmatch(question)
        if match:
            dimension = match.groupdict().get("dimension")
            dimensions = (_DIMENSION_NAMES[dimension],) if dimension else ()
            return QueryIntent(metric=metric_name, dimensions=dimensions)

    match = _TOP_USERS_PATTERN.fullmatch(question)
    if not match:
        return None
    raw_limit = match.group("limit")
    if raw_limit and len(raw_limit) > 4:
        return None
    limit = int(raw_limit) if raw_limit else None
    if limit is None and not match.group("entity").endswith("s"):
        limit = 1
    if limit is not None and not 1 <= limit <= 1000:
        return None
    return QueryIntent(
        metric="top_users_by_completed_revenue",
        limit=limit,
    )


def _compiled_contract_response(node_input: dict[str, Any]) -> dict[str, object]:
    question = node_input["question"]
    intent = node_input["intent"]
    try:
        compiled = compile_query(_CONTRACT, intent)
    except CompileError as error:
        return _refusal_response(
            {
                **node_input,
                "coverage_status": "contract_validation_failed",
                "reason": str(error),
            }
        )

    response = {
        "certified": False,
        "contract_validated": True,
        "intent_assurance": "prototype_full_match_grammar",
        "mode": "contract_compilation",
        "coverage_status": "covered_contract_compiled",
        "metric": compiled.metric,
        "dimensions": list(compiled.dimensions),
        "contract_version": compiled.contract_version,
        "grounding": _response_grounding(node_input),
        "question": question,
        "sql": compiled.sql,
        "parameters": [
            {"name": parameter.name, "value": parameter.value}
            for parameter in compiled.parameters
        ],
        "job_id": None,
        "rows": [],
        "execution_mode": _COMPILE_ONLY,
        "execution_status": "not_executed",
        "credential_mode": "none",
        "truncation_status": "not_applicable",
        "message": (
            "Contract-validated SQL was compiled deterministically. The current "
            "full-match selector is a prototype, so this is not a certified answer."
        ),
    }

    execution_mode = _execution_mode()
    if execution_mode == _COMPILE_ONLY:
        return response
    if execution_mode == _ADK_BIGQUERY_ADC:
        return _execute_with_adk_bigquery_adc(node_input, compiled, response)
    if execution_mode == _ADC_DEVELOPER:
        return _execute_with_adc_developer(node_input, compiled, response)
    return _execution_error_response(
        node_input,
        f"unsupported semantic execution mode: {execution_mode}",
        response,
        execution_mode,
    )


def _execute_with_adk_bigquery_adc(
    node_input: dict[str, Any],
    compiled: Any,
    response: dict[str, object],
) -> dict[str, object]:
    try:
        execution = execute_adk_bigquery_adc_query(
            compiled,
            project=os.getenv("GOOGLE_CLOUD_PROJECT"),
            location=os.getenv("BIGQUERY_LOCATION"),
            max_results=_max_results(),
            maximum_bytes_billed=_maximum_bytes_billed(),
        )
    except ExecutionError as error:
        return _execution_error_response(
            node_input,
            str(error),
            response,
            _ADK_BIGQUERY_ADC,
        )

    return {
        **response,
        "mode": "developer_execution",
        "job_id": execution.job_id,
        "rows": list(execution.rows),
        "execution_mode": execution.execution_mode,
        "execution_status": "succeeded",
        "credential_mode": "adc",
        "developer_mode": True,
        "truncation_status": execution.truncation_status,
        "message": (
            "Contract-validated SQL was executed with ADC through lower-level ADK "
            "BigQuery helpers. This developer result is not end-user certified."
        ),
    }


def _execute_with_adc_developer(
    node_input: dict[str, Any],
    compiled: Any,
    response: dict[str, object],
) -> dict[str, object]:
    try:
        execution = execute_adc_developer_query(
            compiled,
            project=os.getenv("GOOGLE_CLOUD_PROJECT"),
            location=os.getenv("BIGQUERY_LOCATION"),
            max_results=_max_results(),
            maximum_bytes_billed=_maximum_bytes_billed(),
        )
    except ExecutionError as error:
        return _execution_error_response(
            node_input,
            str(error),
            response,
            _ADC_DEVELOPER,
        )

    return {
        **response,
        "mode": "developer_execution",
        "job_id": execution.job_id,
        "rows": list(execution.rows),
        "execution_mode": execution.execution_mode,
        "execution_status": "succeeded",
        "credential_mode": "adc",
        "developer_mode": True,
        "truncation_status": execution.truncation_status,
        "message": (
            "Contract-validated SQL was executed with local ADC. This developer "
            "result is not end-user certified."
        ),
    }


def _refusal_response(node_input: dict[str, Any]) -> dict[str, object]:
    question = node_input["question"]
    coverage_status = node_input.get("coverage_status", "unsupported_contract_intent")
    reason = node_input.get("reason", "No covered semantic contract intent matched.")
    return {
        "certified": False,
        "mode": "out_of_coverage",
        "coverage_status": coverage_status,
        "grounding": _response_grounding(node_input),
        "question": question,
        "reason": reason,
        "message": (
            "This question is outside the certified semantic contract coverage. "
            "No exploratory fallback was invoked."
        ),
    }


def _execution_error_response(
    node_input: dict[str, Any],
    reason: str,
    base_response: dict[str, object] | None = None,
    execution_mode: str | None = None,
) -> dict[str, object]:
    response = base_response or {}
    return {
        **response,
        "certified": False,
        "mode": "execution_error",
        "coverage_status": "contract_execution_failed",
        "execution_mode": execution_mode or response.get("execution_mode"),
        "execution_status": "failed",
        "truncation_status": "unknown",
        "question": node_input["question"],
        "reason": reason,
        "message": (
            "The question matched contract coverage, but developer execution "
            "failed. No exploratory fallback was invoked."
        ),
    }


def _execution_mode() -> str:
    return os.getenv("SEMANTIC_EXECUTION_MODE", _COMPILE_ONLY).strip().lower()


def _grounding_mode() -> str:
    return os.getenv("SEMANTIC_GROUNDING_MODE", _DISABLED).strip().lower()


def _grounding_page_size() -> int:
    raw_value = os.getenv("SEMANTIC_GROUNDING_PAGE_SIZE", "5")
    try:
        return int(raw_value)
    except ValueError:
        raise GroundingError(
            f"SEMANTIC_GROUNDING_PAGE_SIZE must be an integer: {raw_value}"
        )


def _response_grounding(node_input: dict[str, Any]) -> dict[str, object]:
    grounding = node_input.get("grounding")
    if not isinstance(grounding, dict):
        return {
            "status": "missing",
            "mode": _DISABLED,
            "asset_count": 0,
            "used_for_intent_selection": False,
        }
    assets = grounding.get("assets", [])
    asset_count = len(assets) if isinstance(assets, list) else 0
    response = {
        "status": grounding.get("status", "unknown"),
        "mode": grounding.get("mode", _DISABLED),
        "asset_count": asset_count,
        "used_for_intent_selection": False,
    }
    error = grounding.get("error")
    if isinstance(error, str) and error:
        response["error"] = error
    return response


def _max_results() -> int:
    raw_value = os.getenv("SEMANTIC_MAX_RESULTS", "100")
    try:
        return int(raw_value)
    except ValueError:
        raise ExecutionError(f"SEMANTIC_MAX_RESULTS must be an integer: {raw_value}")


def _maximum_bytes_billed() -> int | None:
    raw_value = os.getenv("SEMANTIC_MAXIMUM_BYTES_BILLED", "").strip()
    if not raw_value:
        return None
    try:
        return int(raw_value)
    except ValueError:
        raise ExecutionError(
            f"SEMANTIC_MAXIMUM_BYTES_BILLED must be an integer: {raw_value}"
        )


root_agent = Workflow(
    name="certified_analytics",
    description=("Local ADK 2 workflow for certified semantic-layer SQL compilation."),
    edges=[
        ("START", _normalize_question),
        (_normalize_question, _load_catalog_metadata),
        (_load_catalog_metadata, _select_contract_intent),
        (
            _select_contract_intent,
            {
                "covered": _compiled_contract_response,
                "refuse": _refusal_response,
            },
        ),
    ],
)
