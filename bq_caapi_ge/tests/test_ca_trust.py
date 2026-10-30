"""Tests for Conversational Analytics API trust assessment and streaming."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import warnings

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from google.cloud import geminidataanalytics_v1beta as geminidataanalytics  # noqa: E402
from google.protobuf.json_format import ParseDict  # noqa: E402
import pytest  # noqa: E402

from config.ca_locations import ca_api_endpoint  # noqa: E402
from semantic.ca_trust import (  # noqa: E402
    TrustTier,
    VerifiedQuerySpec,
    build_stateless_chat_request,
    create_chat_client,
    evaluate_ca_stream_trust,
    normalize_prompt_for_match,
    normalize_sql_for_match,
    stream_stateless_chat,
)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "ca_streams"

AUTHORED_VQ_SPEC = VerifiedQuerySpec(
    question="How many completed orders do we have?",
    sql="""SELECT COUNT(DISTINCT order_id) AS completed_order_count
FROM `example-project.example_dataset.orders`
WHERE status = 'completed'""",
    query_id="verified_completed_orders",
)


def _load_fixture(filename: str) -> dict:
    with open(FIXTURES_DIR / filename, encoding="utf-8") as f:
        return json.load(f)


def _rehydrate_messages(raw_messages: list[dict]) -> list[geminidataanalytics.SystemMessage]:
    rehydrated = []
    for m in raw_messages:
        sm = geminidataanalytics.SystemMessage()
        ParseDict(m, sm._pb, ignore_unknown_fields=True)
        rehydrated.append(sm)
    return rehydrated


@pytest.mark.parametrize(
    ("fixture_file", "expected_tier", "expected_sub_mode", "expected_reasons", "use_allowlist"),
    [
        (
            "authored_verified_query.json",
            TrustTier.TIER_1_VERIFIED_OR_COMPILED,
            "AUTHORED_VERIFIED_QUERY",
            (),
            True,
        ),
        (
            "authored_verified_query.json",
            TrustTier.TIER_2_GROUNDED,
            "DYNAMIC_SQL_GROUNDED",
            (),
            False,
        ),
        (
            "three_table_fk_join.json",
            TrustTier.TIER_2_GROUNDED,
            "DYNAMIC_SQL_GROUNDED",
            (),
            False,
        ),
        (
            "trap_aov_priority.json",
            TrustTier.TIER_2_GROUNDED,
            "DYNAMIC_SQL_GROUNDED",
            (),
            False,
        ),
        (
            "trap_total_revenue.json",
            TrustTier.TIER_2_GROUNDED,
            "DYNAMIC_SQL_GROUNDED",
            (),
            False,
        ),
        (
            "trap_active_rate_assumption.json",
            TrustTier.TIER_3_REVIEW_REQUIRED,
            "REVIEW_REQUIRED",
            ("assumption_marker:I assumed",),
            False,
        ),
        (
            "clarification_question.json",
            TrustTier.TIER_3_REVIEW_REQUIRED,
            "CLARIFICATION_OR_REFUSAL",
            ("clarification_or_no_sql",),
            False,
        ),
        (
            "out_of_scope_refusal.json",
            TrustTier.TIER_3_REVIEW_REQUIRED,
            "CLARIFICATION_OR_REFUSAL",
            ("clarification_or_no_sql",),
            False,
        ),
    ],
)
def test_canonical_fixtures_classify_expected_tiers(
    fixture_file: str,
    expected_tier: TrustTier,
    expected_sub_mode: str,
    expected_reasons: tuple[str, ...],
    use_allowlist: bool,
):
    data = _load_fixture(fixture_file)
    q = data.get("question", "Test analytical question")
    raw_msgs = data.get("messages", [])
    allowlist = (AUTHORED_VQ_SPEC,) if use_allowlist else ()

    # 1. Evaluate as raw dicts
    eval_dict = evaluate_ca_stream_trust(raw_msgs, question=q, authored_verified_queries=allowlist)
    assert eval_dict.tier == expected_tier
    assert eval_dict.sub_mode == expected_sub_mode
    assert eval_dict.reasons == expected_reasons

    # 2. Evaluate rehydrated as proto-plus SystemMessage, asserting 0 UserWarnings on text_type == 4
    with warnings.catch_warnings(record=True) as recorded_warnings:
        warnings.simplefilter("always")
        proto_msgs = _rehydrate_messages(raw_msgs)
        eval_proto = evaluate_ca_stream_trust(proto_msgs, question=q, authored_verified_queries=allowlist)

        unrecognized_enum_warnings = [
            w for w in recorded_warnings if issubclass(w.category, UserWarning) and "Unrecognized TextType" in str(w.message)
        ]
        assert len(unrecognized_enum_warnings) == 0

    assert eval_proto.tier == expected_tier
    assert eval_proto.sub_mode == expected_sub_mode
    assert eval_proto.reasons == expected_reasons


def test_live_message_proto_envelope_unwrapping():
    """Real DataChatServiceClient.chat() yields geminidataanalytics.Message envelopes."""
    # Load fixtures and wrap inside real geminidataanalytics.Message objects
    data_3tbl = _load_fixture("three_table_fk_join.json")
    sys_msgs_3tbl = _rehydrate_messages(data_3tbl["messages"])
    envelope_3tbl = [
        geminidataanalytics.Message(
            user_message=geminidataanalytics.UserMessage(text=data_3tbl["question"])
        )
    ] + [
        geminidataanalytics.Message(system_message=sm) for sm in sys_msgs_3tbl
    ]

    class FakeClient:
        def __init__(self, stream):
            self._stream = stream

        def chat(self, request=None, timeout=None):
            return iter(self._stream)

    client_3tbl = FakeClient(envelope_3tbl)
    request_dummy = build_stateless_chat_request(
        project_id="test-p",
        data_agent_name="projects/test-p/locations/global/dataAgents/test-a",
        question=data_3tbl["question"],
    )

    assessment_3tbl = stream_stateless_chat(
        client=client_3tbl,  # type: ignore
        request=request_dummy,
        question=data_3tbl["question"],
    )
    assert assessment_3tbl.tier == TrustTier.TIER_2_GROUNDED
    assert assessment_3tbl.sub_mode == "DYNAMIC_SQL_GROUNDED"
    assert "order_items" in assessment_3tbl.final_sql.lower()
    assert len(assessment_3tbl.result_rows) == 1

    # Test verified query with envelope
    data_vq = _load_fixture("authored_verified_query.json")
    sys_msgs_vq = _rehydrate_messages(data_vq["messages"])
    envelope_vq = [
        geminidataanalytics.Message(
            user_message=geminidataanalytics.UserMessage(text=data_vq["question"])
        )
    ] + [
        geminidataanalytics.Message(system_message=sm) for sm in sys_msgs_vq
    ]
    client_vq = FakeClient(envelope_vq)
    assessment_vq = stream_stateless_chat(
        client=client_vq,  # type: ignore
        request=request_dummy,
        question=data_vq["question"],
        authored_verified_queries=(AUTHORED_VQ_SPEC,),
    )
    assert assessment_vq.tier == TrustTier.TIER_1_VERIFIED_OR_COMPILED
    assert assessment_vq.sub_mode == "AUTHORED_VERIFIED_QUERY"


def test_transport_security_and_credential_isolation():
    """Asserts tokens are bound ONLY to transport gRPC channel and never in request payloads."""
    secret_token = "secret-oauth-token-123"

    request = build_stateless_chat_request(
        project_id="test-proj",
        data_agent_name="projects/test-proj/locations/us/dataAgents/my-agent",
        question="Count completed orders",
        location="us",
    )

    request_repr = repr(request)
    assert secret_token not in request_repr
    assert "conversation_reference" not in request_repr

    # Assert DataAgentContext has no credentials field set
    assert not request.data_agent_context.credentials

    # Client receives transport credentials and regional endpoint
    client = create_chat_client("us", user_access_token=secret_token)
    assert client.api_endpoint == ca_api_endpoint("us")

    # Rejection of empty/whitespace token
    with pytest.raises(ValueError, match="user_access_token cannot be empty"):
        create_chat_client("global", user_access_token="   ")


def test_numeric_reconciliation_adversarial_edge_cases():
    """Tests numeric reconciliation adversarial edge cases and false-positive guards."""
    # 1. Hallucinated $3M with 3 result rows -> unverified
    s1 = [
        {"data": {"generated_sql": "SELECT 1000 AS r", "result": {"name": "res", "data": [{"r": 1000}, {"r": 1000}, {"r": 1000}]}}},
        {"text": {"text_type": 1, "parts": ["Total was $3M across all orders."]}},
    ]
    a1 = evaluate_ca_stream_trust(s1, question="What was total?")
    assert a1.tier == TrustTier.TIER_3_REVIEW_REQUIRED
    assert any("unverified_numeric_in_prose:$3M" in r for r in a1.reasons)

    # 2. Hallucinated 3% with 3 result rows -> unverified
    s2 = [
        {"data": {"generated_sql": "SELECT 1000 AS r", "result": {"name": "res", "data": [{"r": 1000}, {"r": 1000}, {"r": 1000}]}}},
        {"text": {"text_type": 1, "parts": ["Churn rate was 3% in total."]}},
    ]
    a2 = evaluate_ca_stream_trust(s2, question="What was churn?")
    assert a2.tier == TrustTier.TIER_3_REVIEW_REQUIRED
    assert any("unverified_numeric_in_prose:3%" in r for r in a2.reasons)

    # 3. Attached multiplier 3x -> unverified
    s3 = [
        {"data": {"generated_sql": "SELECT 3 AS val", "result": {"name": "res", "data": [{"val": 3.0}]}}},
        {"text": {"text_type": 1, "parts": ["Growth increased by 3x."]}},
    ]
    a3 = evaluate_ca_stream_trust(s3, question="How much did growth increase?")
    assert a3.tier == TrustTier.TIER_3_REVIEW_REQUIRED
    assert any("unverified_numeric_in_prose:3x" in r for r in a3.reasons)

    # 4. Attached currency code 100USD with cell 57 -> unverified
    s4 = [
        {"data": {"generated_sql": "SELECT 57 AS cnt", "result": {"name": "res", "data": [{"cnt": 57}]}}},
        {"text": {"text_type": 1, "parts": ["Balance is 100USD."]}},
    ]
    a4 = evaluate_ca_stream_trust(s4, question="What is balance?")
    assert a4.tier == TrustTier.TIER_3_REVIEW_REQUIRED
    assert any("unverified_numeric_in_prose:100USD" in r for r in a4.reasons)

    # 5. Attached unit 45pct with cell 57 -> unverified
    s5 = [
        {"data": {"generated_sql": "SELECT 57 AS cnt", "result": {"name": "res", "data": [{"cnt": 57}]}}},
        {"text": {"text_type": 1, "parts": ["Share is 45pct."]}},
    ]
    a5 = evaluate_ca_stream_trust(s5, question="What is share?")
    assert a5.tier == TrustTier.TIER_3_REVIEW_REQUIRED
    assert any("unverified_numeric_in_prose:45pct" in r for r in a5.reasons)

    # 6. Attached unit $2.5bn -> unverified
    s6 = [
        {"data": {"generated_sql": "SELECT 2.5 AS amt", "result": {"name": "res", "data": [{"amt": 2.5}]}}},
        {"text": {"text_type": 1, "parts": ["Revenue reached $2.5bn."]}},
    ]
    a6 = evaluate_ca_stream_trust(s6, question="What was revenue?")
    assert a6.tier == TrustTier.TIER_3_REVIEW_REQUIRED
    assert any("unverified_numeric_in_prose:$2.5bn" in r for r in a6.reasons)

    # 7. Unicode minus −500 vs +500 cell -> unverified
    s7 = [
        {"data": {"generated_sql": "SELECT 500 AS amt", "result": {"name": "res", "data": [{"amt": 500}]}}},
        {"text": {"text_type": 1, "parts": ["Profit was −500."]}},
    ]
    a7 = evaluate_ca_stream_trust(s7, question="What was profit?")
    assert a7.tier == TrustTier.TIER_3_REVIEW_REQUIRED
    assert any("unverified_numeric_in_prose:-500" in r for r in a7.reasons)

    # 8. Question-echo bypass blocked for limit-less question: "customers with over 100 orders" -> "There were 100 orders" with cell 57
    s8 = [
        {"data": {"generated_sql": "SELECT 57 AS cnt", "result": {"name": "res", "data": [{"cnt": 57}]}}},
        {"text": {"text_type": 1, "parts": ["There were 100 orders."]}},
    ]
    a8 = evaluate_ca_stream_trust(s8, question="Find customers with over 100 orders")
    assert a8.tier == TrustTier.TIER_3_REVIEW_REQUIRED
    assert any("unverified_numeric_in_prose:100" in r for r in a8.reasons)

    # 9. Markdown bullet "- 43" when cell has 43 -> reconciled!
    s9 = [
        {"data": {"generated_sql": "SELECT 43 AS cnt", "result": {"name": "res", "data": [{"cnt": 43}]}}},
        {"text": {"text_type": 1, "parts": ["Results:\n- 43"]}},
    ]
    a9 = evaluate_ca_stream_trust(s9, question="Get results")
    assert a9.tier == TrustTier.TIER_2_GROUNDED

    # 10. Range "10 - 20" when cells have 10 and 20 -> reconciled!
    s10 = [
        {"data": {"generated_sql": "SELECT 10 AS lo, 20 AS hi", "result": {"name": "res", "data": [{"lo": 10, "hi": 20}]}}},
        {"text": {"text_type": 1, "parts": ["The range was 10 - 20."]}},
    ]
    a10 = evaluate_ca_stream_trust(s10, question="What was range?")
    assert a10.tier == TrustTier.TIER_2_GROUNDED

    # 11. Currency threshold echo in question ("orders over $100") with cell 57 -> unverified!
    s11 = [
        {"data": {"generated_sql": "SELECT 57 AS cnt", "result": {"name": "res", "data": [{"cnt": 57}]}}},
        {"text": {"text_type": 1, "parts": ["Total revenue was $100."]}},
    ]
    a11 = evaluate_ca_stream_trust(s11, question="Find customers with orders over $100")
    assert a11.tier == TrustTier.TIER_3_REVIEW_REQUIRED
    assert any("unverified_numeric_in_prose:$100" in r for r in a11.reasons)

    # 12. ISO date with valid row date ("Peak on 2026-01-15 at 57") -> reconciled!
    s12 = [
        {"data": {"generated_sql": "SELECT '2026-01-15' AS d, 57 AS val", "result": {"name": "res", "data": [{"d": "2026-01-15", "val": 57}]}}},
        {"text": {"text_type": 1, "parts": ["Peak on 2026-01-15 at 57."]}},
    ]
    a12 = evaluate_ca_stream_trust(s12, question="What was the peak?")
    assert a12.tier == TrustTier.TIER_2_GROUNDED

    # 13. Benign identifier preceding negative number ("Q3 -500"): reconciled vs -500, flagged vs +500!
    s13 = [
        {"data": {"generated_sql": "SELECT -500 AS profit", "result": {"name": "res", "data": [{"profit": -500}]}}},
        {"text": {"text_type": 1, "parts": ["Q3 -500 was recorded."]}},
    ]
    a13 = evaluate_ca_stream_trust(s13, question="What was Q3 profit?")
    assert a13.tier == TrustTier.TIER_2_GROUNDED

    s13_neg = [
        {"data": {"generated_sql": "SELECT 500 AS profit", "result": {"name": "res", "data": [{"profit": 500}]}}},
        {"text": {"text_type": 1, "parts": ["Q3 -500 was recorded."]}},
    ]
    a13_neg = evaluate_ca_stream_trust(s13_neg, question="What was Q3 profit?")
    assert a13_neg.tier == TrustTier.TIER_3_REVIEW_REQUIRED
    assert "unverified_numeric_in_prose:-500" in a13_neg.reasons

    # 14. Preceding count before negative number ("dropped 10 -500"): reconciled vs -500, flagged vs +500!
    s14 = [
        {"data": {"generated_sql": "SELECT 10 AS drop_cnt, -500 AS val", "result": {"name": "res", "data": [{"drop_cnt": 10, "val": -500}]}}},
        {"text": {"text_type": 1, "parts": ["Dropped 10 -500 units."]}},
    ]
    a14 = evaluate_ca_stream_trust(s14, question="What dropped?")
    assert a14.tier == TrustTier.TIER_2_GROUNDED

    s14_neg = [
        {"data": {"generated_sql": "SELECT 10 AS drop_cnt, 500 AS val", "result": {"name": "res", "data": [{"drop_cnt": 10, "val": 500}]}}},
        {"text": {"text_type": 1, "parts": ["Dropped 10 -500 units."]}},
    ]
    a14_neg = evaluate_ca_stream_trust(s14_neg, question="What dropped?")
    assert a14_neg.tier == TrustTier.TIER_3_REVIEW_REQUIRED
    assert "unverified_numeric_in_prose:-500" in a14_neg.reasons

    # 15. Tight range without spaces ("10-20") with cells 10 and 20 -> reconciled!
    s15 = [
        {"data": {"generated_sql": "SELECT 10 AS lo, 20 AS hi", "result": {"name": "res", "data": [{"lo": 10, "hi": 20}]}}},
        {"text": {"text_type": 1, "parts": ["Spread was 10-20."]}},
    ]
    a15 = evaluate_ca_stream_trust(s15, question="What was spread?")
    assert a15.tier == TrustTier.TIER_2_GROUNDED

    # 16. Scientific notation ("1.5e6") -> flagged as unverified!
    s16 = [
        {"data": {"generated_sql": "SELECT 1.5 AS val", "result": {"name": "res", "data": [{"val": 1.5}]}}},
        {"text": {"text_type": 1, "parts": ["Scaled value was 1.5e6."]}},
    ]
    a16 = evaluate_ca_stream_trust(s16, question="What was scaled value?")
    assert a16.tier == TrustTier.TIER_3_REVIEW_REQUIRED
    assert any("unverified_numeric_in_prose:1.5e6" in r for r in a16.reasons)

    # 17. Underscore-grouped number ("3_000") -> flagged as unverified!
    s17 = [
        {"data": {"generated_sql": "SELECT 3000 AS val", "result": {"name": "res", "data": [{"val": 3000}]}}},
        {"text": {"text_type": 1, "parts": ["Volume was 3_000."]}},
    ]
    a17 = evaluate_ca_stream_trust(s17, question="What was volume?")
    assert a17.tier == TrustTier.TIER_3_REVIEW_REQUIRED
    assert any("unverified_numeric_in_prose:3_000" in r for r in a17.reasons)


def test_normalize_sql_string_literal_preservation():
    """SQL string literals (single and double quoted) retain exact casing and preserve comments."""
    assert normalize_prompt_for_match("what_was_the_total_revenue?") == "what was the total revenue"

    sql1 = "SELECT * FROM orders WHERE status = 'Completed'"
    sql2 = "SELECT * FROM orders WHERE status = 'completed'"
    assert normalize_sql_for_match(sql1) != normalize_sql_for_match(sql2)

    sql_comment_inside = "SELECT 'foo -- bar' AS col"
    norm_comment = normalize_sql_for_match(sql_comment_inside)
    assert "'foo -- bar'" in norm_comment

    sql_dq = 'SELECT "Status Name" FROM orders WHERE status = "Completed"'
    norm_dq = normalize_sql_for_match(sql_dq)
    assert '"Status Name"' in norm_dq
    assert '"Completed"' in norm_dq

    sql_apostrophe_comment_a = "-- don't ignore case\nSELECT 'X' AS flag -- it's upper"
    sql_apostrophe_comment_b = "-- don't ignore case\nSELECT 'x' AS flag -- it's lower"
    assert normalize_sql_for_match(sql_apostrophe_comment_a) != normalize_sql_for_match(sql_apostrophe_comment_b)


def test_strict_wire_vq_requires_thought_and_result_name():
    """Model-chosen result name 'verified_query' without THOUGHT signature stays Tier 2."""
    stream = [
        {"data": {"generated_sql": AUTHORED_VQ_SPEC.sql, "result": {"name": "verified_query", "data": [{"completed_order_count": 116.0}]}}},
        {"text": {"text_type": 1, "parts": ["There were 116 completed orders."]}},
    ]
    assessment = evaluate_ca_stream_trust(
        stream,
        question=AUTHORED_VQ_SPEC.question,
        authored_verified_queries=(AUTHORED_VQ_SPEC,),
    )
    # Stays Tier 2 because wire THOUGHT signature was missing!
    assert assessment.tier == TrustTier.TIER_2_GROUNDED
    assert assessment.sub_mode == "DYNAMIC_SQL_GROUNDED"


def test_verified_query_result_missing_thought_sql():
    """When result is verified_query but wire lacks THOUGHT or SQL, sub-mode is REVIEW_REQUIRED."""
    stream = [
        {"data": {"result": {"name": "verified_query", "data": [{"val": 10}]}}},
        {"text": {"text_type": 1, "parts": ["Count is 10."]}},
    ]
    assessment = evaluate_ca_stream_trust(stream, question="Count?")
    assert assessment.tier == TrustTier.TIER_3_REVIEW_REQUIRED
    assert assessment.sub_mode == "REVIEW_REQUIRED"
    assert "verified_query_thought_missing" in assessment.reasons
    assert "clarification_or_no_sql" in assessment.reasons


def test_compiled_sql_match_and_mismatch():
    """compiled_sql parameter gates TIER_1 STRICT_CONTRACT_COMPILED."""
    stream = [
        {"data": {"generated_sql": "SELECT COUNT(1) AS c FROM t", "result": {"name": "r", "data": [{"c": 10}]}}},
        {"text": {"text_type": 1, "parts": ["Count is 10."]}},
    ]
    # 1. Matching compiled SQL -> Tier 1
    a_match = evaluate_ca_stream_trust(
        stream,
        question="Count?",
        compiled_sql="SELECT COUNT(1) AS c FROM t;",
    )
    assert a_match.tier == TrustTier.TIER_1_VERIFIED_OR_COMPILED
    assert a_match.sub_mode == "STRICT_CONTRACT_COMPILED"

    # 2. Mismatched compiled SQL -> Tier 3
    a_mismatch = evaluate_ca_stream_trust(
        stream,
        question="Count?",
        compiled_sql="SELECT COUNT(1) AS c FROM orders;",
    )
    assert a_mismatch.tier == TrustTier.TIER_3_REVIEW_REQUIRED
    assert "compiled_sql_mismatch" in a_mismatch.reasons

    # 3. Whitespace/empty compiled_sql with no executed SQL -> Tier 3 (never Tier 2)
    stream_no_sql = [
        {"data": {"result": {"name": "r", "data": [{"c": 10}]}}},
        {"text": {"text_type": 1, "parts": ["Count is 10."]}},
    ]
    a_empty_compiled = evaluate_ca_stream_trust(
        stream_no_sql,
        question="Count?",
        compiled_sql="   ",
    )
    assert a_empty_compiled.tier == TrustTier.TIER_3_REVIEW_REQUIRED
    assert "compiled_sql_mismatch" in a_empty_compiled.reasons


def test_trailing_unexecuted_sql_and_empty_final_response():
    """Trailing unexecuted SQL or empty final response with data routes to Tier 3."""
    # 1. Trailing unexecuted SQL (e.g. DELETE FROM t)
    stream_trailing = [
        {"data": {"generated_sql": "SELECT 1 AS val", "result": {"name": "r", "data": [{"val": 1}]}}},
        {"text": {"text_type": 1, "parts": ["Result is 1."]}},
        {"data": {"generated_sql": "DELETE FROM t"}},
    ]
    a_trailing = evaluate_ca_stream_trust(stream_trailing, question="Run delete?")
    assert a_trailing.tier == TrustTier.TIER_3_REVIEW_REQUIRED
    assert "unexecuted_trailing_sql" in a_trailing.reasons

    # 2. Data result but empty final response
    stream_empty_resp = [
        {"data": {"generated_sql": "SELECT 1 AS val", "result": {"name": "r", "data": [{"val": 1}]}}},
    ]
    a_empty = evaluate_ca_stream_trust(stream_empty_resp, question="Run?")
    assert a_empty.tier == TrustTier.TIER_3_REVIEW_REQUIRED
    assert "empty_final_response" in a_empty.reasons


def test_example_queries_server_signal_alone_never_promoted():
    """Server-derived example_queries without allowlist or wire VQ is never promoted to Tier 1."""
    stream = [
        {"data": {"generated_sql": "SELECT 1", "result": {"name": "query_res", "data": [{"val": 1.0}]}}},
        {"example_queries": [{"question": "Q?", "sql": "SELECT 1"}]},
        {"text": {"text_type": 1, "parts": ["1"]}},
    ]
    assessment = evaluate_ca_stream_trust(stream, question="Q?")
    assert assessment.tier == TrustTier.TIER_2_GROUNDED
    assert assessment.sub_mode == "DYNAMIC_SQL_GROUNDED"


def test_verified_query_prompt_mismatch_downgrades_to_tier_3():
    """Q2 verified SQL replayed on a Q3 question triggers mismatch downgrade to Tier 3."""
    stream = [
        {"text": {"text_type": 2, "parts": ["Matched a verified query", AUTHORED_VQ_SPEC.sql]}},
        {"data": {"result": {"name": "verified_query", "data": [{"completed_order_count": 116.0}]}}},
        {"text": {"text_type": 1, "parts": ["There were 116 completed orders."]}},
    ]
    assessment = evaluate_ca_stream_trust(
        stream,
        question="What was our Q3 completed order count?",
        authored_verified_queries=(AUTHORED_VQ_SPEC,),
    )
    assert assessment.tier == TrustTier.TIER_3_REVIEW_REQUIRED
    assert "verified_query_prompt_mismatch" in assessment.reasons


def test_clean_exploratory_query_stays_tier_2():
    """A clean intermediate SELECT DISTINCT followed by final aggregate query is Tier 2."""
    stream = [
        {"data": {"generated_sql": "SELECT DISTINCT status FROM orders", "result": {"name": "intermediate", "data": [{"status": "completed"}]}}},
        {"data": {"generated_sql": "SELECT COUNT(1) AS c FROM orders WHERE status = 'completed'", "result": {"name": "final", "data": [{"c": 116.0}]}}},
        {"text": {"text_type": 1, "parts": ["116 completed orders."]}},
    ]
    assessment = evaluate_ca_stream_trust(stream, question="How many completed orders?")
    assert assessment.tier == TrustTier.TIER_2_GROUNDED
    assert assessment.exploratory_query_count == 1
    assert assessment.error_retry_count == 0


def test_error_retry_downgrades_to_tier_3():
    """Any error message or un-resulted SQL retry downgrades to Tier 3."""
    stream = [
        {"data": {"generated_sql": "SELECT * FROM non_existent_table"}},
        {"error": {"code": 3, "message": "Table not found"}},
        {"data": {"generated_sql": "SELECT * FROM orders", "result": {"name": "res", "data": [{"id": 1.0}]}}},
        {"text": {"text_type": 1, "parts": ["Result: 1"]}},
    ]
    assessment = evaluate_ca_stream_trust(stream, question="Get orders")
    assert assessment.tier == TrustTier.TIER_3_REVIEW_REQUIRED
    assert assessment.error_retry_count >= 1
    assert "error_recovery_retry" in assessment.reasons


def test_analysis_postprocessing_downgrades_to_tier_3():
    """Analysis post-processing chunk forces Tier 3 review."""
    stream = [
        {"data": {"generated_sql": "SELECT 100 AS total", "result": {"name": "res", "data": [{"total": 100.0}]}}},
        {"analysis": {"content": "Data indicates healthy revenue."}},
        {"text": {"text_type": 1, "parts": ["Total is 100."]}},
    ]
    assessment = evaluate_ca_stream_trust(stream, question="What is total?")
    assert assessment.tier == TrustTier.TIER_3_REVIEW_REQUIRED
    assert "analysis_postprocessing_present" in assessment.reasons


def test_thought_assumptions_ignored_when_final_response_is_clean():
    """Thoughts containing assumption markers do NOT trigger assumption_marker if final_response is clean."""
    stream = [
        {"text": {"text_type": 2, "parts": ["Assuming active means customer has orders..."]}},
        {"data": {"generated_sql": "SELECT 10 AS total", "result": {"name": "res", "data": [{"total": 10.0}]}}},
        {"text": {"text_type": 1, "parts": ["Total count is 10."]}},
    ]
    assessment = evaluate_ca_stream_trust(stream, question="Count active")
    assert assessment.tier == TrustTier.TIER_2_GROUNDED


def test_mid_stream_exception_returns_incomplete_stream():
    """Mid-stream exception produces INCOMPLETE_STREAM assessment."""
    class CrashingStream:
        def __iter__(self):
            yield {"text": {"text_type": 1, "parts": ["Partial response"]}}
            raise TimeoutError("Deadline exceeded mid-stream")

    class CrashingClient:
        def chat(self, request=None, timeout=None):
            return CrashingStream()

    request = build_stateless_chat_request(
        project_id="p", data_agent_name="projects/p/locations/global/dataAgents/a", question="q"
    )
    assessment = stream_stateless_chat(
        client=CrashingClient(),  # type: ignore
        request=request,
        question="q",
    )
    assert assessment.tier == TrustTier.TIER_3_REVIEW_REQUIRED
    assert assessment.sub_mode == "INCOMPLETE_STREAM"
    assert "incomplete_stream" in assessment.reasons
    assert any("stream_error:TimeoutError" in r for r in assessment.reasons)
