"""Semantic context, contract, catalog retrieval, execution, and CA API trust utilities."""

from __future__ import annotations

import importlib
from typing import Any

_EXPORTS: dict[str, tuple[str, str]] = {
    # compiler
    "CompiledMetricQuery": ("semantic.compiler", "CompiledMetricQuery"),
    "CoverageError": ("semantic.compiler", "CoverageError"),
    "FilterClause": ("semantic.compiler", "FilterClause"),
    "compile_metric_query": ("semantic.compiler", "compile_metric_query"),
    # graph_export
    "GraphExportError": ("semantic.graph_export", "GraphExportError"),
    "GraphExportResult": ("semantic.graph_export", "GraphExportResult"),
    "SkippedGraphMetric": ("semantic.graph_export", "SkippedGraphMetric"),
    "build_data_agent_datasource_references": ("semantic.graph_export", "build_data_agent_datasource_references"),
    "export_fk_constraints_ddl": ("semantic.graph_export", "export_fk_constraints_ddl"),
    "export_property_graph_ddl": ("semantic.graph_export", "export_property_graph_ddl"),
    "export_verified_queries": ("semantic.graph_export", "export_verified_queries"),
    # guardrails
    "DryRunSummary": ("semantic.guardrails", "DryRunSummary"),
    "SqlPolicyError": ("semantic.guardrails", "SqlPolicyError"),
    "validate_dry_run_summary": ("semantic.guardrails", "validate_dry_run_summary"),
    # numeric_reconcile
    "has_assumption_markers": ("semantic.numeric_reconcile", "has_assumption_markers"),
    "reconcile_prose_numbers": ("semantic.numeric_reconcile", "reconcile_prose_numbers"),
    # sql_lex
    "extract_qualified_columns": ("semantic.sql_lex", "extract_qualified_columns"),
    "format_googlesql_string_literal": ("semantic.sql_lex", "format_googlesql_string_literal"),
    "has_multiple_statements": ("semantic.sql_lex", "has_multiple_statements"),
    "parse_single_aggregate": ("semantic.sql_lex", "parse_single_aggregate"),
    "rewrite_base_table_qualifiers": ("semantic.sql_lex", "rewrite_base_table_qualifiers"),
    "strip_sql_literals_and_comments": ("semantic.sql_lex", "strip_sql_literals_and_comments"),
    # types
    "VerifiedQuerySpec": ("semantic.types", "VerifiedQuerySpec"),
    # ca_trust (only loaded on access)
    "TrustTier": ("semantic.ca_trust", "TrustTier"),
    "TrustAssessment": ("semantic.ca_trust", "TrustAssessment"),
    "create_chat_client": ("semantic.ca_trust", "create_chat_client"),
    "build_stateless_chat_request": ("semantic.ca_trust", "build_stateless_chat_request"),
    "stream_stateless_chat": ("semantic.ca_trust", "stream_stateless_chat"),
    "evaluate_ca_stream_trust": ("semantic.ca_trust", "evaluate_ca_stream_trust"),
    # rls_impersonation (only loaded on access)
    "ImpersonationError": ("semantic.rls_impersonation", "ImpersonationError"),
    "RoleAssertion": ("semantic.rls_impersonation", "RoleAssertion"),
    "build_impersonated_credentials": ("semantic.rls_impersonation", "build_impersonated_credentials"),
    "mint_hmac_role_assertion": ("semantic.rls_impersonation", "mint_hmac_role_assertion"),
    "parse_role_sa_map": ("semantic.rls_impersonation", "parse_role_sa_map"),
    "redact_service_account_emails": ("semantic.rls_impersonation", "redact_service_account_emails"),
    "verify_role_assertion": ("semantic.rls_impersonation", "verify_role_assertion"),
}

__all__ = list(_EXPORTS.keys())


def __getattr__(name: str) -> Any:
    if name in _EXPORTS:
        module_name, attr_name = _EXPORTS[name]
        module = importlib.import_module(module_name)
        val = getattr(module, attr_name)
        globals()[name] = val
        return val
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + __all__)
