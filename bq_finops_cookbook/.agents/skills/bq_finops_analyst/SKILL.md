---
name: bq-finops-analyst
description: |
  Analyzes BigQuery slot utilization, workload characteristics (stability, burstiness), and database cost structures.
  Recommends optimal capacity management strategies (on-demand vs autoscaling vs committed) conforming to GCP product rules.
  Applies Standard/Enterprise edition-specific constraints and verified INFORMATION_SCHEMA views using MCP-first querying.
metadata:
  version: v1.0.0
  publisher: local
  framework: antigravity
---

# BigQuery FinOps Analyst Skill

This skill allows an Antigravity (`agy`) main agent or delegated subagent to perform an end-to-end BigQuery cost and compute resource (slots) optimization analysis. It utilizes a 6-step analysis workflow to produce highly tailored, data-driven capacity recommendations.

---

## 1. Prerequisites and Context

Before running any SQL queries or checking CLI parameters, you must initialize your analysis context:
1. **Load Guidelines & Logic:** View and read [finops_agent.md](file:///Users/johanesa/Developer/git/random-stuff/bq_finops_cookbook/.agents/skills/bq_finops_analyst/resources/finops_agent.md) to understand the full set of SQL query references, fallback logic, and decision metrics.
2. **Retrieve Official Docs:** Read [REFERENCES.md](file:///Users/johanesa/Developer/git/random-stuff/bq_finops_cookbook/.agents/skills/bq_finops_analyst/resources/REFERENCES.md) for quick-reference URLs of Google Cloud specifications.

---

## 2. Mandatory Rules & Guardrails

*   **Location Scope:** All `INFORMATION_SCHEMA` queries are region-scoped. You **must** replace `region-[YOUR_REGION]` with the user-specified region (e.g., `region-us`, `region-eu`, `region-asia-northeast1`). Never mix different regions in a single analysis.
*   **MCP-First Execution:** Always execute SQL via BigQuery MCP tools (e.g., `execute_sql`). Only fall back to running the `bq` CLI when the MCP tool is unavailable or has insufficient capabilities.
*   **Read-Only Safety:** This analysis is strictly read-only. You must never create, edit, delete, or assign any reservations. Generate command proposals only.
*   **Standard Edition Constraints:** Standard Edition has severe product restrictions. If Standard Edition is targeted or detected:
    *   No baseline slots are supported (`slot_capacity` must be 0/omitted).
    *   Only project-level assignments are supported (no folder or organization-level assignments).
    *   No target job concurrency / advanced workload management is supported.
*   **CLI Mutex Rules:** In reservation creations (`bq mk --reservation`), the flag `--autoscale_max_slots` is mutually exclusive with `--max_slots` and `--scaling_mode`. Never combine them.

---

## 3. Detailed 6-Step Workflow

Execute each of the following steps sequentially, writing your outputs directly into the `analysis_results/` folder as structured Markdown files.

### Step 1: Assess Current Configuration
*   **Goal:** Discover if the user currently uses reservations or commitments, and measure current baseline utilization.
*   **Queries to run:** (from `finops_agent.md`)
    *   Query 0.1 (List Reservations)
    *   Query 0.2 (Reservation Assignments) - *Note: The `state` column has been removed from this query. If an error occurs, inspect the view schema first.*
    *   Query 0.2a (Historical Commitments)
    *   Query 0.3 (Current Utilization)
    *   Query 0.4 (Idle Slots)
    *   Query 0.5 (On-Demand / Unassigned Workloads)
*   **Output:** If any reservations or commitments exist, write `analysis_results/00_current_configuration.md`.

### Step 2: Analyze Slot Metrics & Percentiles
*   **Goal:** Compute percentile distributions and characterize the core workload behavior.
*   **Queries to run:**
    *   Query 1.1 (System-Wide Percentiles)
    *   Query 1.2 (Top Consumers)
    *   Query 1.3 (Granular Hourly/Daily Patterns)
*   **Formulas and Metrics to Calculate:**
    *   **Stability (CV):** `stddev_slots / avg_slots`.
        *   *CV < 0.5:* Stable/Low variability
        *   *CV 0.5 - 1.0:* Moderate variability
        *   *CV > 1.0:* Highly variable
    *   **Burstiness (Burst Ratio):** `p95_slots / p50_slots`.
        *   *Ratio < 2.0:* Low burstiness
        *   *Ratio 2.0 - 4.0:* Medium burstiness
        *   *Ratio > 4.0:* High burstiness
*   **Output:** Write `analysis_results/01_slot_metrics.md`, `analysis_results/02_top_consumers.md`, and `analysis_results/03_usage_patterns.md`.

### Step 3: Identify Optimization Opportunities
*   **Goal:** Uncover slow/expensive queries, contention issues, error profiles, and pending queues.
*   **Queries to run:**
    *   Query 4.1 (Slot Contention Insights)
    *   Query 4.2 (Expensive Queries by Identity)
    *   Query 4.3 (Slow Queries)
    *   Query 4.4 (Reservation Capacity Simulation)
    *   Query 4.5 (Usage Trends over Time)
    *   Query 4.8 (Job Errors - focusing on rate limits, quota limits, resources exceeded)
    *   Query 4.9 (Job Impact at different slot sizes)
    *   Query 4.10 (Queue Pressure & Interactive query limits)
    *   Query 4.11 (Official BigQuery Slot Recommender - if active)
*   **Output:** Write `analysis_results/04_optimization_opportunities.md`.

### Step 4: Storage & Cost Analysis
*   **Goal:** Analyze active/long-term storage splits, old/unused tables, and streaming ingestion modes.
*   **Queries to run:**
    *   Query 6.1 (Storage Analysis by Table)
    *   Query 6.2 (Unused tables older than 90 days)
    *   Query 5.1 (Streaming Ingestion Monitoring)
*   **Heuristics:**
    *   If tables have >90% long-term storage, check if they are actually being queried.
    *   If legacy streaming ingestion is used, calculate the 50% storage ingestion cost savings from migrating to the Storage Write API.
*   **Output:** Write `analysis_results/05_storage_and_cost.md`.

### Step 5: Formulate Final Recommendation
*   **Goal:** Provide the executive summary and clear, source-backed, step-by-step implementation proposals.
*   **Strategy Heuristics:**
    *   *On-Demand:* Best if overall compute usage is low, highly spiky, or idle waste would dominate.
    *   *Autoscaling Reservations:* Best for moderate to high utilization with distinct peaks (Standard or Enterprise edition depending on feature requirements).
    *   *Committed Reservations:* Recommended only if the stable baseline (CV < 0.5, low burst) is consistently high enough to offset operational risk.
*   **Verify syntax and options:** Double-check your proposed command options using official docs. Make sure Standard Edition proposals do not include baseline slots or non-project assignments.
*   **Output:** Write `analysis_results/06_final_recommendation.md`. Ensure it includes a `Documentation Checks` section citing URLs of the GCP docs reviewed, and an `MCP / bq Execution Notes` section.

### Step 6: Present Results
*   Once all reports are saved in `analysis_results/`, present the concise executive summary and recommended capacity strategy specified in `06_final_recommendation.md` to the user in the main conversation window.

---

## 4. Interaction Tips for Antigravity (agy) Desktop

When executed inside `agy` Desktop, the subagent can utilize the browser view, terminal commands, or file view. Maintain short, concise steps, and keep context clean. Do not load large query tables directly into memory; summarize statistics in markdown format to preserve the context window when running under Gemini 3.5 Flash (Medium/High).
