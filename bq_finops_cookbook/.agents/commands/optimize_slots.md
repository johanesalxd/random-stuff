---
description: Orchestrates BigQuery slot optimization analysis and generates actionable recommendations
argument-hint: <project_id> <region>
---

# BigQuery Slot Optimization Workflow

Orchestrates the analysis of BigQuery slot usage to recommend the optimal workload management strategy (On-Demand vs. Reservations).

## Usage

Ask the agent:
> "Follow the workflow in .agents/commands/optimize_slots.md to analyze project <PROJECT_ID> in <REGION>"

**Example**:
> "Follow the workflow in .agents/commands/optimize_slots.md to analyze project my-gcp-project in region-us"

## Description

This workflow orchestrates a 5-step analysis process:

1.  **Assess Current Configuration**: Identify existing reservations and assignments.
2.  **Analyze Slot Metrics**: Calculate percentiles, stability, and burstiness.
3.  **Identify Opportunities**: Find top consumers and optimization targets.
4.  **Generate Recommendation**: Recommend a strategy (On-Demand, Baseline, Autoscaling, Hybrid).
5.  **Storage & Cost Analysis**: Analyze storage costs and on-demand spend.
6.  **Generate Reports**: Detailed markdown reports in `analysis_results/`.

## Workflow

### Step 1: Initialize Analysis
Use the `Task` tool with `subagent_type='general'` and the content of `.agents/agents/finops_agent.md` as the prompt context.

Provide the following task description:
```
Analyze BigQuery slot usage for:
- Project ID: <project_id>
- Region: <region>

Execute the complete 6-step analysis process defined in the agent instructions.
Generate all reports in the 'analysis_results/' directory.
```

### Step 2: User Presentation

**Present the results to the user**:

```
Analysis Complete.

**Executive Summary**:
- **Strategy**: [Strategy Name] (e.g., "Autoscaling Reservations")
- **Confidence**: [High/Medium/Low]
- **Key Metric**: [Mention one key metric, e.g., "CV = 1.5 indicates high variability"]
- **Estimated Monthly Spend**: [Sum of Compute + Storage]

**Reports Generated**:
The following detailed reports have been generated in `analysis_results/`:
1. `00_current_configuration.md` (if applicable)
2. `01_slot_metrics.md`
3. `02_top_consumers.md`
4. `03_usage_patterns.md`
5. `04_optimization_opportunities.md`
6. `05_storage_and_cost.md`
7. `06_final_recommendation.md`

**Next Steps**:
Please review the `06_final_recommendation.md` file for the specific implementation plan and commands.
```

## Parameters

-   **project_id** (required): The GCP project ID where compute occurs.
-   **region** (required): The BigQuery region (e.g., `us`, `eu`, `asia-northeast1`).

## Outputs

1.  **Metric Reports**: `analysis_results/` (00-05)
2.  **Final Recommendation**: `analysis_results/06_final_recommendation.md`
