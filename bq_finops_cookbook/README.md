# BigQuery Slot Optimization Framework

A comprehensive framework for analyzing BigQuery slot utilization and optimizing workload performance.

**Note:** This framework integrates proven queries and patterns from [Google Cloud's BigQuery Utils](https://github.com/GoogleCloudPlatform/bigquery-utils/tree/master/dashboards/system_tables) to provide enhanced historical analysis and granular utilization insights.

## Overview

This framework helps BigQuery administrators and data platform teams make data-driven decisions about workload management strategies. By analyzing historical usage patterns, it recommends the optimal approach: staying on-demand, committing to baseline slots, using autoscaling, or implementing a hybrid strategy.

## Quick Reference

### When to Stay On-Demand (PAYG)
- Average slots < 100
- High variability (CV > 1.0)
- Sporadic, unpredictable usage
- Development/testing environments

### When to Use Autoscaling Reservations (Standard Edition)
- High burst ratio (p95/p50 > 3)
- Bursty workloads without baseline needs
- Pay slot-hours (no commitments available)

### When to Use Baseline Reservations (Enterprise/Enterprise Plus)
- p25 slots ≥ 50 (meets minimum)
- Stable workloads needing guaranteed capacity
- Choose: Pay slot-hours OR purchase commitments (1-year/3-year for discounts)
- Can add autoscaling on top (always pay-as-you-go)

### When to Use Hybrid Approach
- Multiple distinct workload types
- Some projects stable (prod), others variable (dev/test)
- Can separate workloads by project

### What This Framework Does

- Analyzes 30 days of slot usage patterns
- Calculates workload stability and burstiness metrics
- Recommends optimal workload management strategy
- Identifies optimization opportunities
- Generates detailed reports

### Who Should Use This

- BigQuery administrators managing multi-project environments
- Data platform engineers planning capacity
- Performance optimization teams
- Organizations with significant BigQuery compute workloads

### Expected Outcomes

- Clear understanding of current slot utilization patterns
- Data-backed recommendation for workload management strategy
- Identification of performance optimization opportunities
- Actionable implementation plan with specific commands
- Baseline for ongoing monitoring and optimization

## Thought Process

### Why Slot Optimization Matters

BigQuery offers multiple workload management models:
- **On-Demand (PAYG):** Flexible capacity, pay per query
- **Reservations:** Dedicated capacity with different pricing options
  - **Standard Edition:** Autoscaling only, pay slot-hours
  - **Enterprise/Enterprise Plus:** Baseline (+ optional autoscaling), choose slot-hours or commitments

Choosing the wrong model can result in:
- **Resource Waste:** Paying for committed slots that sit idle
- **Performance Issues:** Insufficient capacity during peak loads causing query slowdowns
- **Slot Contention:** Queries competing for limited resources

### Analysis Methodology

The framework follows a systematic approach:

```mermaid
graph TD
    A[Start: User has BigQuery Project] --> B[Step 0: Assess Current Config]
    B --> C{Has Existing<br/>Reservations?}
    C -->|Yes| D[Analyze Current Utilization]
    C -->|No| E[Step 1: Analyze Slot Usage]
    D --> E
    E --> F[Step 2: Calculate Metrics]
    F --> G[Step 3: Determine Strategy]
    G --> H[Step 4: Identify Optimizations]
    H --> I[Step 5: Generate Report]
    I --> J[Implement Changes]
    J --> K[Monitor & Validate]
```

### Decision Framework Logic

```mermaid
graph TD
    A[Workload Metrics] --> B{Avg Slots < 100?}
    B -->|Yes| C{High Variability<br/>CV > 1.0?}
    B -->|No| D{p25 >= 50?}
    C -->|Yes| E[Stay On-Demand]
    C -->|No| F{p25 >= 50?}
    D -->|Yes| G{Need Guaranteed<br/>Baseline?}
    D -->|No| E
    F -->|Yes| H{Need Guaranteed<br/>Baseline?}
    F -->|No| E
    G -->|Yes| I[Baseline Reservations<br/>Enterprise/Enterprise Plus]
    G -->|No| J[Autoscaling Reservations<br/>Standard Edition]
    H -->|Yes| I
    H -->|No| K[Hybrid Approach<br/>Mixed Strategy]
```

## How to Use

### Prerequisites

Before starting the analysis, ensure you have:

- [ ] BigQuery Resource Viewer role (`roles/bigquery.resourceViewer`)
- [ ] Access to `INFORMATION_SCHEMA.JOBS_BY_PROJECT` and `INFORMATION_SCHEMA.JOBS_TIMELINE_BY_PROJECT`
- [ ] Project ID where compute occurs
- [ ] Region where compute occurs (e.g., `us`, `eu`, `asia-northeast1`)
- [ ] AI assistant with MCP server access (bigquery-data-analytics, bigquery-conversational-analytics)

### Step-by-Step Instructions

**Step 1: Prepare Your Request**

Provide your AI assistant with the following information:

```
Based on the guidance in 'bq_finops_cookbook/finops_prompt.md', please help me analyze
my project [YOUR_PROJECT_ID], which has compute and storage in the [YOUR_REGION] region.

Please list your plan before execution.
```

**Step 2: Review the Analysis Plan**

The AI assistant will outline the analysis steps:
- Step 0: Assess current configuration
- Step 1: Analyze slot usage patterns
- Step 2: Calculate workload metrics
- Step 3: Recommend strategy
- Step 4: Identify optimizations
- Step 5: Generate reports

**Step 3: Execute the Analysis**

The AI assistant will:
1. Run SQL queries against your project's INFORMATION_SCHEMA
2. Calculate stability and burstiness metrics
3. Analyze current reservations (if any)
4. Identify optimization opportunities
5. Generate detailed reports

**Step 4: Review Generated Reports**

Reports will be created in the `analysis_results/` directory:
- `00_current_configuration.md` - Current reservation setup (if applicable)
- `01_slot_metrics.md` - Percentiles, variability, burstiness
- `02_top_consumers.md` - Project breakdown
- `03_usage_patterns.md` - Hourly/daily patterns
- `04_optimization_opportunities.md` - Contention, expensive queries, performance insights
- `05_final_recommendation.md` - Strategy and implementation plan

**Step 5: Implement Recommendations**

Follow the implementation steps in the final recommendation report. This typically includes:
- Creating or modifying reservations
- Assigning projects to reservations
- Setting up monitoring queries
- Validating the changes

## Output Structure

The `analysis_results/` directory contains:

```
analysis_results/
├── 00_current_configuration.md (if reservations exist)
├── 01_slot_metrics.md
├── 02_top_consumers.md
├── 03_usage_patterns.md
├── 04_optimization_opportunities.md
└── 05_final_recommendation.md
```

Each report provides detailed analysis and actionable recommendations. See the generated files for complete details.

## Additional Resources

### Official Documentation
- [BigQuery Reservations Introduction](https://cloud.google.com/bigquery/docs/reservations-intro)
- [INFORMATION_SCHEMA.JOBS View](https://cloud.google.com/bigquery/docs/information-schema-jobs)
- [INFORMATION_SCHEMA.JOBS_TIMELINE View](https://cloud.google.com/bigquery/docs/information-schema-jobs-timeline)
- [Workload Management Best Practices](https://cloud.google.com/bigquery/docs/best-practices-performance-compute)
- [BigQuery Editions](https://cloud.google.com/bigquery/docs/editions-intro)

### Related Guides
- `finops_prompt.md` - Detailed analysis guide with all SQL queries
- `analysis_results/` - Generated reports from your analysis
