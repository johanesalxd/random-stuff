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

from semantic.runtime import (  # noqa: E402
    SEMANTIC_SELECTION_INSTRUCTION,
    SemanticSelection,
    finish_catalog_broad_resolution,
    finish_semantic_narrow_resolution,
    load_semantic_registry,
    recover_invalid_semantic_selection,
    resolve_semantic_selection,
)

semantic_selector = LlmAgent(
    name="semantic_context_selector",
    model=os.getenv("MODEL_NAME", "gemini-2.5-flash"),
    instruction=SEMANTIC_SELECTION_INSTRUCTION,
    output_schema=SemanticSelection,
    after_model_callback=recover_invalid_semantic_selection,
)

root_agent = Workflow(
    name="semantic_analytics",
    description="Resolves reusable semantic context before catalog grounding.",
    edges=[
        ("START", load_semantic_registry, semantic_selector),
        (semantic_selector, resolve_semantic_selection),
        (
            resolve_semantic_selection,
            {
                "semantic_narrow": finish_semantic_narrow_resolution,
                "catalog_broad": finish_catalog_broad_resolution,
            },
        ),
    ],
)
