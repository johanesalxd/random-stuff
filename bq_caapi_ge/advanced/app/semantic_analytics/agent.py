"""V2 semantic-first analytics workflow."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

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
    SUMMARIZE_RESULT_INSTRUCTION,
    enter_sql_generation,
    execute_sql_once,
    finish_answer,
    finish_query_error,
    prepare_result_summary,
)

_DEFAULT_SELECTOR_MODEL = "gemini-3.5-flash"
_DEFAULT_SQL_MODEL = "claude-sonnet-5"
_DEFAULT_SUMMARIZER_MODEL = "gemini-3.5-flash"


def build_model(model_name: str) -> Any:
    """Builds an ADK model value for Gemini or Vertex-hosted Claude.

    Args:
        model_name: Configured model identifier.

    Returns:
        A Gemini model string or explicit ADK Claude model object.

    Raises:
        RuntimeError: If Claude support is not installed.
    """
    if not model_name.startswith("claude-"):
        return model_name
    try:
        from google.adk.models.anthropic_llm import Claude
    except ImportError as error:
        raise RuntimeError(
            "Claude models require the anthropic[vertex] dependency"
        ) from error
    return Claude(model=model_name)


semantic_selector = LlmAgent(
    name="semantic_context_selector",
    model=build_model(os.getenv("SEMANTIC_SELECTOR_MODEL", _DEFAULT_SELECTOR_MODEL)),
    instruction=SEMANTIC_SELECTION_INSTRUCTION,
    output_schema=SemanticSelection,
    after_model_callback=recover_invalid_semantic_selection,
)

sql_generator = LlmAgent(
    name="semantic_sql_generator",
    model=build_model(os.getenv("SQL_GENERATOR_MODEL", _DEFAULT_SQL_MODEL)),
    instruction=GENERATE_SQL_INSTRUCTION,
)

result_summarizer = LlmAgent(
    name="query_result_summarizer",
    model=build_model(os.getenv("RESULT_SUMMARIZER_MODEL", _DEFAULT_SUMMARIZER_MODEL)),
    instruction=SUMMARIZE_RESULT_INSTRUCTION,
)


def build_root_agent(
    *,
    selector_model=None,
    generator_model=None,
    summarizer_model=None,
):
    """Builds the V2 Workflow with injectable model boundaries.

    Args:
        selector_model: Optional semantic-selector model override.
        generator_model: Optional SQL-generator model override.
        summarizer_model: Optional result-summarizer model override.

    Returns:
        Configured semantic analytics Workflow.
    """
    selector = _with_model(semantic_selector, selector_model)
    generator = _with_model(sql_generator, generator_model)
    summarizer = _with_model(result_summarizer, summarizer_model)

    return Workflow(
        name="semantic_analytics",
        description="Grounds semantic context, executes SQL once, and summarizes rows.",
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
            (generator, execute_sql_once),
            (
                execute_sql_once,
                {
                    "success": prepare_result_summary,
                    "error": finish_query_error,
                },
            ),
            (prepare_result_summary, summarizer),
            (summarizer, finish_answer),
        ],
    )


def _with_model(agent: LlmAgent, model: Any) -> LlmAgent:
    if model is None:
        return agent
    return agent.model_copy(update={"model": model, "parent_agent": None})


root_agent = build_root_agent()
