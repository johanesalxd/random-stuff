"""Client-side Conversational Analytics API trust assessment and streaming.

Provides transport-safe stateless chat helpers and a 3-tier trust classification
engine that audits Conversational Analytics API streams without storing credentials
in payload structures or relying on server-side example_queries metadata alone.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
import re
from typing import Any

from google.api_core.client_options import ClientOptions
from google.api_core.exceptions import GoogleAPICallError
from google.cloud import geminidataanalytics_v1beta as geminidataanalytics
from google.oauth2.credentials import Credentials
from google.protobuf.json_format import MessageToDict
import grpc

from config.ca_locations import ca_api_endpoint
from semantic.numeric_reconcile import (
    _ASSUMPTION_PATTERN,
    has_assumption_markers,
    reconcile_prose_numbers,
)
from semantic.sql_lex import strip_sql_literals_and_comments
from semantic.types import VerifiedQuerySpec

__all__ = [
    "TrustTier",
    "VerifiedQuerySpec",
    "TrustAssessment",
    "has_assumption_markers",
    "reconcile_prose_numbers",
    "normalize_sql_for_match",
    "normalize_prompt_for_match",
    "create_chat_client",
    "build_stateless_chat_request",
    "stream_stateless_chat",
    "evaluate_ca_stream_trust",
]


class TrustTier(str, Enum):
    """Trust hierarchy for Conversational Analytics API analytical outputs."""

    TIER_1_VERIFIED_OR_COMPILED = "TIER_1_VERIFIED_OR_COMPILED"
    TIER_2_GROUNDED = "TIER_2_GROUNDED"
    TIER_3_REVIEW_REQUIRED = "TIER_3_REVIEW_REQUIRED"


@dataclass(frozen=True)
class TrustAssessment:
    """Result of stream-level Conversational Analytics trust classification."""

    tier: TrustTier
    sub_mode: str
    reasons: tuple[str, ...] = ()
    final_response: str = ""
    final_sql: str | None = None
    result_rows: tuple[dict[str, Any], ...] = ()
    exploratory_query_count: int = 0
    error_retry_count: int = 0
    uses_graph_expand: bool = False
    uses_agg_measures: bool = False


def normalize_sql_for_match(sql: str | None) -> str:
    """Normalizes a SQL query for canonical comparison, preserving string literals."""
    if not sql:
        return ""
    literals: list[str] = []

    def _tokenize(match: re.Match) -> str:
        tok = match.group(0)
        if tok.startswith("--") or tok.startswith("/*"):
            return " "
        literals.append(tok)
        return f"__LITERAL_{len(literals) - 1}__"

    s = re.sub(
        r"'(?:''|\\'|[^'])*'|\"(?:\"\"|\\\"|[^\"])*\"|--[^\n]*|/\*[\s\S]*?\*/",
        _tokenize,
        sql,
    )
    s = s.replace("`", "")
    s = re.sub(r"\s+", " ", s).strip().lower()
    s = s.rstrip(";")

    return re.sub(r"__literal_(\d+)__", lambda m: literals[int(m.group(1))], s)


def normalize_prompt_for_match(prompt: str | None) -> str:
    """Normalizes prompt text for fuzzy comparison."""
    if not prompt:
        return ""
    s = re.sub(r"[\W_]+", " ", prompt)
    return re.sub(r"\s+", " ", s).strip().lower()


def create_chat_client(
    location: str = "global",
    *,
    user_access_token: str | None = None,
) -> geminidataanalytics.DataChatServiceClient:
    """Creates a transport-safe CA API DataChatServiceClient.

    Args:
        location: Google Cloud region or multi-region (e.g. 'global', 'us', 'eu').
        user_access_token: Optional OAuth bearer access token. If provided, binds
            transport credentials directly to the gRPC channel.

    Returns:
        Configured DataChatServiceClient.

    Raises:
        ValueError: If user_access_token is empty or whitespace.
    """
    if user_access_token is not None:
        token = user_access_token.strip()
        if not token:
            raise ValueError("user_access_token cannot be empty or whitespace.")
        credentials = Credentials(token=token)
    else:
        credentials = None

    client_options = ClientOptions(api_endpoint=ca_api_endpoint(location))
    return geminidataanalytics.DataChatServiceClient(
        credentials=credentials,
        client_options=client_options,
    )


def build_stateless_chat_request(
    *,
    project_id: str,
    data_agent_name: str,
    question: str,
    location: str = "global",
) -> geminidataanalytics.ChatRequest:
    """Builds a stateless Conversational Analytics ChatRequest.

    Non-persistence of query result rows requires 3 client-side guardrails:
      1. Stateless ChatRequest: never set conversation_reference.
      2. Agent logging disabled: Conversation / BigQuery Agent Analytics logging
         is disabled on the target data agent resource.
      3. Client non-persistence: The calling application does not persist DataResult.

    Security Notice:
      Never sets DataAgentContext.credentials. That proto field is exclusively for
      Looker OAuth integration; for BigQuery sources it is ignored so queries execute
      under the Conversational Analytics gRPC channel owner identity, bypassing per-user
      row-level and column-level security and exposing bearer tokens in proto repr.
      End-user OAuth tokens must be bound to DataChatServiceClient(credentials=...)
      on the gRPC channel via create_chat_client().

    Args:
        project_id: Target Google Cloud project ID.
        data_agent_name: Full data agent resource name.
        question: User prompt or analytical question.
        location: CA API location.

    Returns:
        geminidataanalytics.ChatRequest configured for stateless streaming.

    Raises:
        ValueError: If any required parameter is empty or whitespace.
    """
    if not project_id or not project_id.strip():
        raise ValueError("project_id cannot be empty or whitespace.")
    if not data_agent_name or not data_agent_name.strip():
        raise ValueError("data_agent_name cannot be empty or whitespace.")
    if not question or not question.strip():
        raise ValueError("question cannot be empty or whitespace.")
    if not location or not location.strip():
        raise ValueError("location cannot be empty or whitespace.")

    return geminidataanalytics.ChatRequest(
        parent=f"projects/{project_id.strip()}/locations/{location.strip()}",
        messages=[
            geminidataanalytics.Message(
                user_message=geminidataanalytics.UserMessage(text=question.strip())
            )
        ],
        data_agent_context=geminidataanalytics.DataAgentContext(
            data_agent=data_agent_name.strip()
        ),
    )


def stream_stateless_chat(
    *,
    client: geminidataanalytics.DataChatServiceClient,
    request: geminidataanalytics.ChatRequest,
    question: str,
    authored_verified_queries: Sequence[VerifiedQuerySpec] = (),
    compiled_sql: str | None = None,
    timeout: float | None = 120.0,
) -> TrustAssessment:
    """Streams a stateless chat request and classifies the resulting response stream.

    Catches mid-stream transport or gRPC exceptions and delegates to
    evaluate_ca_stream_trust with stream_complete=False to produce an INCOMPLETE_STREAM
    tier-3 assessment.
    """
    buffered_messages: list[Any] = []
    stream_complete = True
    stream_error: str | None = None
    try:
        response_stream = client.chat(request=request, timeout=timeout)
        for msg in response_stream:
            buffered_messages.append(msg)
    except (GoogleAPICallError, grpc.RpcError, TimeoutError, OSError) as exc:
        stream_complete = False
        stream_error = type(exc).__name__

    return evaluate_ca_stream_trust(
        buffered_messages,
        question=question,
        stream_complete=stream_complete,
        stream_error=stream_error,
        authored_verified_queries=authored_verified_queries,
        compiled_sql=compiled_sql,
    )


def _reconcile_prose_numbers(
    prose: str,
    *,
    question: str,
    result_rows: Sequence[Mapping[str, Any]],
) -> list[str]:
    """Backwards-compatible wrapper delegating to reconcile_prose_numbers."""
    return list(reconcile_prose_numbers(prose, question=question, result_rows=result_rows))


def _build_assessment(
    tier: TrustTier,
    sub_mode: str,
    *,
    reasons: tuple[str, ...] = (),
    final_response: str = "",
    final_sql: str | None = None,
    result_rows: tuple[dict[str, Any], ...] = (),
    exploratory_query_count: int = 0,
    error_retry_count: int = 0,
    uses_graph_expand: bool = False,
    uses_agg_measures: bool = False,
) -> TrustAssessment:
    return TrustAssessment(
        tier=tier,
        sub_mode=sub_mode,
        reasons=reasons,
        final_response=final_response,
        final_sql=final_sql,
        result_rows=result_rows,
        exploratory_query_count=exploratory_query_count,
        error_retry_count=error_retry_count,
        uses_graph_expand=uses_graph_expand,
        uses_agg_measures=uses_agg_measures,
    )


def evaluate_ca_stream_trust(
    messages: Iterable[geminidataanalytics.Message | geminidataanalytics.SystemMessage | Mapping[str, Any]],
    *,
    question: str,
    stream_complete: bool = True,
    stream_error: str | None = None,
    authored_verified_queries: Sequence[VerifiedQuerySpec] = (),
    compiled_sql: str | None = None,
) -> TrustAssessment:
    """Classifies a Conversational Analytics API message stream into trust tiers."""
    final_response_chunks: list[str] = []
    matched_vq_sql: str | None = None
    last_executed_sql: str | None = None
    last_result_name: str | None = None
    result_rows: list[dict[str, Any]] = []
    has_data_result = False
    has_analysis = False
    error_retry_count = 0
    successful_queries = 0
    in_flight_sql: str | None = None

    for raw_msg in messages:
        if isinstance(raw_msg, Mapping):
            msg = dict(raw_msg)
        elif hasattr(raw_msg, "_pb"):
            msg = MessageToDict(raw_msg._pb, preserving_proto_field_name=True, use_integers_for_enums=True)
        elif hasattr(raw_msg, "DESCRIPTOR"):
            msg = MessageToDict(raw_msg, preserving_proto_field_name=True, use_integers_for_enums=True)
        else:
            msg = {}

        # Unwrap live geminidataanalytics.Message envelope
        if "system_message" in msg or "systemMessage" in msg:
            inner = msg.get("system_message") or msg.get("systemMessage")
            if isinstance(inner, Mapping):
                msg = dict(inner)
            else:
                continue
        elif "user_message" in msg or "userMessage" in msg:
            continue

        if "error" in msg and msg["error"]:
            error_retry_count += 1

        if "analysis" in msg and msg["analysis"]:
            has_analysis = True

        text_chunk = msg.get("text")
        if isinstance(text_chunk, Mapping):
            raw_text_type = text_chunk.get("text_type", text_chunk.get("textType", 0))
            if isinstance(raw_text_type, str):
                text_type = {
                    "FINAL_RESPONSE": 1,
                    "THOUGHT": 2,
                    "PROGRESS": 3,
                }.get(raw_text_type.upper(), 0)
            else:
                try:
                    text_type = int(raw_text_type)
                except (ValueError, TypeError):
                    text_type = 0
            parts = text_chunk.get("parts", [])
            if text_type == 1:
                joined_text = "".join(str(p) for p in parts if p is not None)
                if joined_text:
                    final_response_chunks.append(joined_text)
            elif text_type == 2:
                if len(parts) >= 2 and str(parts[0]).strip() == "Matched a verified query":
                    matched_vq_sql = str(parts[1]).strip()

        data_chunk = msg.get("data")
        if isinstance(data_chunk, Mapping) and data_chunk:
            gen_sql = data_chunk.get("generated_sql") or data_chunk.get("generatedSql")
            if gen_sql:
                if in_flight_sql is not None:
                    error_retry_count += 1
                in_flight_sql = str(gen_sql)
                # An exploratory or dynamic query clears prior matched VQ SQL
                matched_vq_sql = None

            res = data_chunk.get("result")
            if isinstance(res, Mapping):
                has_data_result = True
                last_result_name = res.get("name")
                rows = res.get("data", res.get("rows", []))
                if isinstance(rows, list):
                    result_rows = [dict(r) for r in rows if isinstance(r, Mapping)]
                successful_queries += 1
                if last_result_name == "verified_query" and matched_vq_sql is not None:
                    last_executed_sql = matched_vq_sql
                elif in_flight_sql is not None:
                    last_executed_sql = in_flight_sql
                in_flight_sql = None

    final_response = "\n\n".join(final_response_chunks)
    exploratory_query_count = (successful_queries - 1) if (successful_queries > 1 and error_retry_count == 0) else 0

    # Pair final_sql with executed result; if trailing in_flight_sql remained, keep it for evidence
    effective_sql = last_executed_sql or in_flight_sql

    uses_graph_expand = False
    uses_agg_measures = False
    if effective_sql:
        stripped = strip_sql_literals_and_comments(effective_sql)
        uses_graph_expand = bool(re.search(r"(?<![A-Za-z0-9_`])GRAPH_EXPAND\s*\(", stripped, re.IGNORECASE))
        uses_agg_measures = bool(re.search(r"(?<![A-Za-z0-9_`])AGG\s*\(", stripped, re.IGNORECASE))

    if not stream_complete:
        stream_reasons = ("incomplete_stream", f"stream_error:{stream_error}") if stream_error else ("incomplete_stream",)
        return _build_assessment(
            TrustTier.TIER_3_REVIEW_REQUIRED,
            "INCOMPLETE_STREAM",
            reasons=stream_reasons,
            final_response=final_response,
            final_sql=effective_sql,
            result_rows=tuple(result_rows),
            exploratory_query_count=0,
            error_retry_count=error_retry_count,
            uses_graph_expand=uses_graph_expand,
            uses_agg_measures=uses_agg_measures,
        )

    compiled_sql_clean = compiled_sql.strip() if compiled_sql else None
    if not has_data_result:
        return _build_assessment(
            TrustTier.TIER_3_REVIEW_REQUIRED,
            "CLARIFICATION_OR_REFUSAL",
            reasons=("clarification_or_no_sql",),
            final_response=final_response,
            final_sql=effective_sql,
            result_rows=tuple(result_rows),
            exploratory_query_count=exploratory_query_count,
            error_retry_count=error_retry_count,
            uses_graph_expand=uses_graph_expand,
            uses_agg_measures=uses_agg_measures,
        )

    if effective_sql is None and compiled_sql is None:
        reasons_list = ["clarification_or_no_sql"]
        if last_result_name == "verified_query":
            reasons_list.append("verified_query_thought_missing")
        return _build_assessment(
            TrustTier.TIER_3_REVIEW_REQUIRED,
            "REVIEW_REQUIRED" if last_result_name == "verified_query" else "CLARIFICATION_OR_REFUSAL",
            reasons=tuple(reasons_list),
            final_response=final_response,
            final_sql=effective_sql,
            result_rows=tuple(result_rows),
            exploratory_query_count=exploratory_query_count,
            error_retry_count=error_retry_count,
            uses_graph_expand=uses_graph_expand,
            uses_agg_measures=uses_agg_measures,
        )

    reasons: list[str] = []
    if error_retry_count > 0:
        reasons.append("error_recovery_retry")
    if in_flight_sql is not None:
        reasons.append("unexecuted_trailing_sql")
    if has_analysis:
        reasons.append("analysis_postprocessing_present")
    if has_data_result and not final_response.strip():
        reasons.append("empty_final_response")

    assumption_match = _ASSUMPTION_PATTERN.search(final_response)
    if assumption_match:
        reasons.append(f"assumption_marker:{assumption_match.group(0)}")

    unverified_numerics = _reconcile_prose_numbers(
        final_response,
        question=question,
        result_rows=result_rows,
    )
    for num_token in unverified_numerics:
        reasons.append(f"unverified_numeric_in_prose:{num_token}")

    # Strict dual wire confirmation for verified query:
    # Requires THOUGHT signature AND last_result_name == "verified_query" AND zero trailing SQL AND zero retries
    is_wire_vq = (
        last_result_name == "verified_query"
        and matched_vq_sql is not None
        and in_flight_sql is None
        and error_retry_count == 0
    )

    allowlist_matched_spec = False
    if is_wire_vq and authored_verified_queries:
        norm_effective = normalize_sql_for_match(effective_sql)
        norm_q = normalize_prompt_for_match(question)
        allowlist_matched_spec = any(
            normalize_sql_for_match(spec.sql) == norm_effective
            and normalize_prompt_for_match(spec.question) == norm_q
            for spec in authored_verified_queries
        )
        if not allowlist_matched_spec:
            reasons.append("verified_query_prompt_mismatch")

    # Compiled SQL verification
    compiled_sql_matched = False
    if compiled_sql is not None:
        if compiled_sql_clean and has_data_result and effective_sql:
            if normalize_sql_for_match(effective_sql) == normalize_sql_for_match(compiled_sql_clean):
                compiled_sql_matched = True
            else:
                reasons.append("compiled_sql_mismatch")
        else:
            reasons.append("compiled_sql_mismatch")

    if reasons:
        return _build_assessment(
            TrustTier.TIER_3_REVIEW_REQUIRED,
            "REVIEW_REQUIRED",
            reasons=tuple(reasons),
            final_response=final_response,
            final_sql=effective_sql,
            result_rows=tuple(result_rows),
            exploratory_query_count=exploratory_query_count,
            error_retry_count=error_retry_count,
            uses_graph_expand=uses_graph_expand,
            uses_agg_measures=uses_agg_measures,
        )

    if compiled_sql_matched:
        return _build_assessment(
            TrustTier.TIER_1_VERIFIED_OR_COMPILED,
            "STRICT_CONTRACT_COMPILED",
            reasons=(),
            final_response=final_response,
            final_sql=effective_sql,
            result_rows=tuple(result_rows),
            exploratory_query_count=exploratory_query_count,
            error_retry_count=error_retry_count,
            uses_graph_expand=uses_graph_expand,
            uses_agg_measures=uses_agg_measures,
        )

    if is_wire_vq and allowlist_matched_spec:
        return _build_assessment(
            TrustTier.TIER_1_VERIFIED_OR_COMPILED,
            "AUTHORED_VERIFIED_QUERY",
            reasons=(),
            final_response=final_response,
            final_sql=effective_sql,
            result_rows=tuple(result_rows),
            exploratory_query_count=exploratory_query_count,
            error_retry_count=error_retry_count,
            uses_graph_expand=uses_graph_expand,
            uses_agg_measures=uses_agg_measures,
        )

    sub_mode = "GRAPH_MEASURE_GROUNDED" if (uses_graph_expand and uses_agg_measures) else "DYNAMIC_SQL_GROUNDED"
    return _build_assessment(
        TrustTier.TIER_2_GROUNDED,
        sub_mode,
        reasons=(),
        final_response=final_response,
        final_sql=effective_sql,
        result_rows=tuple(result_rows),
        exploratory_query_count=exploratory_query_count,
        error_retry_count=error_retry_count,
        uses_graph_expand=uses_graph_expand,
        uses_agg_measures=uses_agg_measures,
    )
