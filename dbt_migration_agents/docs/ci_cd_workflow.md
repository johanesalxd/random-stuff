# AI Validation Agent CI/CD Workflow

This document outlines the automated workflow for validating PR changes using AI agents.

## Overview

The goal is to automate the validation of dbt model changes in a CI/CD pipeline. Instead of manual code review, an AI agent compares the "Production" version of a table against the "PR" version to ensure data integrity and correctness.

## Workflow Steps

### 1. Environment Setup (`scripts/setup_profile.py`)
- Dynamically creates a `profiles.yml` for the session.
- Defines two targets:
  - `dev`: Represents the current Production environment (`sample_gold`).
  - `ci`: Represents the temporary PR environment (`sample_gold_ci`).

### 2. Simulation (`scripts/simulate_pr.py`)
Orchestrates the "Before" vs "After" scenario without modifying source code.

- **Step 1: Establish Baseline (Prod)**
  - Runs `uv run dbt run --select fct_orders_broken --target dev`
  - Creates: `sample_gold.fct_orders_broken` (The "current" state with issues)

- **Step 2: Build PR Version (CI)**
  - Runs `uv run dbt run --select fct_orders --target ci`
  - Creates: `sample_gold_ci.fct_orders` (The "proposed" fixed version)

- **Step 3: AI Validation Trigger**
  - Calls `scripts/ci_validation_runner.py` with:
    - **Prod Table:** `[project].sample_gold.fct_orders_broken`
    - **PR Table:** `[project].sample_gold_ci.fct_orders`
    - **Model:** `gemini-3-pro-preview`

### 3. The AI "Brain" (`scripts/ci_validation_runner.py`)
Acts as the bridge between the CI pipeline and Vertex AI.

1.  **Context Loading:**
    - Reads `.agents/agents/validation_subagent.md` (System Prompt).
    - Reads `migration_validator/VALIDATION_COOKBOOK.md` (Guidelines).
2.  **Analysis:**
    - Fetches table schemas for both tables using BigQuery API.
3.  **Prompting:**
    - Sends Context + Schemas to **Gemini 3 Pro**.
    - Request: "Write a Python script to validate the PR table against the Prod table."
4.  **Execution:**
    - Extracts the Python code block from the AI response.
    - Executes the script locally using `uv run python`.
    - Captures the output (Pass/Fail/Metrics).

## Usage

```bash
# Install dependencies
uv pip install google-cloud-aiplatform google-cloud-bigquery dbt-bigquery pyyaml

# Run the full simulation
uv run python scripts/simulate_pr.py
```
