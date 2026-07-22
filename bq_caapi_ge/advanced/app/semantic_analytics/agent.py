"""ADK workflow for domain-neutral semantic context resolution."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from google.adk.agents import LlmAgent
from google.adk.workflow import Workflow

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from semantic.catalog_runtime import (  # noqa: E402
    assess_broad_context,
    assess_context,
    finish_clarification,
    load_broad_catalog_context,
    load_narrow_catalog_context,
)
from semantic.runtime import (  # noqa: E402
    SEMANTIC_SELECTION_INSTRUCTION,
    SemanticSelection,
    load_semantic_registry,
    recover_invalid_semantic_selection,
    resolve_semantic_selection,
)
from semantic.sql_runtime import (  # noqa: E402
    GENERATE_SQL_INSTRUCTION,
    GeneratedSql,
    dry_run_sql,
    enforce_sql_policy,
    enter_sql_generation,
    finish_sql_refusal,
    finish_sql_result,
    maybe_execute_sql,
    recover_invalid_sql,
    repair_sql,
)

semantic_selector = LlmAgent(
    name="semantic_context_selector",
    model=os.getenv("MODEL_NAME", "gemini-2.5-flash"),
    instruction=SEMANTIC_SELECTION_INSTRUCTION,
    output_schema=SemanticSelection,
    after_model_callback=recover_invalid_semantic_selection,
)

sql_generator = LlmAgent(
    name="guarded_sql_generator",
    model=os.getenv("MODEL_NAME", "gemini-2.5-flash"),
    instruction=GENERATE_SQL_INSTRUCTION,
    output_schema=GeneratedSql,
    after_model_callback=recover_invalid_sql,
)

root_agent = Workflow(
    name="semantic_analytics",
    description="Grounds semantic context and generates guarded, read-only SQL.",
    edges=[
        ("START", load_semantic_registry, semantic_selector),
        (semantic_selector, resolve_semantic_selection),
        (
            resolve_semantic_selection,
            {
                "semantic_narrow": load_narrow_catalog_context,
                "catalog_broad": load_broad_catalog_context,
            },
        ),
        (load_narrow_catalog_context, assess_context),
        (
            assess_context,
            {
                "sufficient": enter_sql_generation,
                "insufficient": load_broad_catalog_context,
            },
        ),
        (load_broad_catalog_context, assess_broad_context),
        (
            assess_broad_context,
            {
                "grounded": enter_sql_generation,
                "clarify": finish_clarification,
            },
        ),
        (enter_sql_generation, sql_generator),
        (sql_generator, enforce_sql_policy),
        (
            enforce_sql_policy,
            {
                "allowed": dry_run_sql,
                "rejected": repair_sql,
            },
        ),
        (
            dry_run_sql,
            {
                "valid": maybe_execute_sql,
                "invalid": repair_sql,
            },
        ),
        (
            repair_sql,
            {
                "retry": sql_generator,
                "exhausted": finish_sql_refusal,
            },
        ),
        (maybe_execute_sql, finish_sql_result),
    ],
)
