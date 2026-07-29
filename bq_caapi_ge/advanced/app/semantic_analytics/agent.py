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
    model=os.getenv("MODEL_NAME", "gemini-3.5-flash"),
    instruction=SEMANTIC_SELECTION_INSTRUCTION,
    output_schema=SemanticSelection,
    after_model_callback=recover_invalid_semantic_selection,
)

sql_generator = LlmAgent(
    name="guarded_sql_generator",
    model=os.getenv("MODEL_NAME", "gemini-3.5-flash"),
    instruction=GENERATE_SQL_INSTRUCTION,
    output_schema=GeneratedSql,
    after_model_callback=recover_invalid_sql,
)


def build_root_agent(
    *,
    selector_model=None,
    generator_model=None,
):
    """Build the semantic-analytics Workflow with injectable model boundaries.

    The default selector and generator agents are reused unless a replacement
    model is supplied, in which case the corresponding agent is copied with the
    scripted model detached from any parent. This lets hermetic tests drive the
    full graph with a deterministic ``BaseLlm`` while production keeps the
    configured Gemini model.

    Args:
        selector_model: Optional model override for the semantic selector agent.
        generator_model: Optional model override for the SQL generator agent.

    Returns:
        A configured ``Workflow`` root agent.
    """
    selector = (
        semantic_selector.model_copy(
            update={"model": selector_model, "parent_agent": None}
        )
        if selector_model is not None
        else semantic_selector
    )
    generator = (
        sql_generator.model_copy(
            update={"model": generator_model, "parent_agent": None}
        )
        if generator_model is not None
        else sql_generator
    )

    return Workflow(
        name="semantic_analytics",
        description=("Grounds semantic context and generates guarded, read-only SQL."),
        edges=[
            ("START", load_semantic_registry, selector),
            (selector, resolve_semantic_selection),
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
            (enter_sql_generation, generator),
            (generator, enforce_sql_policy),
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
                    "unauthorized": finish_sql_refusal,
                },
            ),
            (
                repair_sql,
                {
                    "retry": generator,
                    "exhausted": finish_sql_refusal,
                },
            ),
            (maybe_execute_sql, finish_sql_result),
        ],
    )


root_agent = build_root_agent()
