# BigQuery Slot Optimization Framework

A comprehensive framework for analyzing BigQuery slot utilization and optimizing workload performance.

## Overview

This framework helps BigQuery administrators and data platform teams make data-driven decisions about workload management strategies. By analyzing historical usage patterns, it recommends the optimal approach: staying on-demand, committing to baseline slots, using autoscaling, or implementing a hybrid strategy.

## Quick Reference

### When to Stay On-Demand (PAYG)
- Average slots < 100
- High variability (CV > 1.0)
- Sporadic, unpredictable usage
- Development/testing environments

### When to Use Baseline Commitment
- p25 slots ≥ 50 (meets minimum)
- Low variability (CV < 1.0)
- Stable baseline with manageable peaks
- Production workloads with consistent patterns

### When to Use Autoscaling (Enterprise Plus)
- p25 slots ≥ 50 (baseline requirement)
- High burst ratio (p95/p50 > 3)
- Predictable peak patterns
- Need guaranteed capacity during bursts

### When to Use Hybrid Approach
- Multiple distinct workload types
- Some projects stable (prod), others variable (dev/test)
- Can separate workloads by project

**Note:** If Mermaid diagrams don't render in your viewer, view this file on GitHub or use a Mermaid-compatible markdown viewer.

### What This Framework Does

- Analyzes 30 days of BigQuery slot usage patterns
- Assesses current reservation configurations (if any)
- Calculates workload stability and burstiness metrics
- Recommends optimal workload management strategy based on performance characteristics
- Identifies specific performance optimization opportunities
- Generates detailed reports for stakeholder review

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
- **On-Demand (PAYG):** Flexible capacity, scales automatically
- **Flat-Rate Commitments:** Dedicated capacity, predictable performance
- **Autoscaling:** Dynamic capacity adjustment (Enterprise Plus edition)

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
    I --> J{Satisfied with<br/>Recommendations?}
    J -->|No| K[Refine Analysis]
    K --> E
    J -->|Yes| L[Implement Changes]
    L --> M[Monitor & Validate]
```

### Decision Framework Logic

```mermaid
graph TD
    A[Workload Metrics] --> B{Avg Slots < 100?}
    B -->|Yes| C{High Variability<br/>CV > 1.0?}
    B -->|No| D{p25 >= 50?}
    C -->|Yes| E[Stay On-Demand]
    C -->|No| F{p25 >= 50?}
    D -->|Yes| G{High Burst<br/>p95/p50 > 3?}
    D -->|No| E
    F -->|Yes| H{Stable Baseline?}
    F -->|No| E
    G -->|Yes| I[Autoscaling Commitment<br/>Enterprise Plus]
    G -->|No| J[Baseline Commitment<br/>Standard/Enterprise]
    H -->|Yes| J
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

## Quick Start Example

### Scenario

Analyze project `your-project-id` in the `us` region.

### User Request

```
Based on the guidance in 'bq_finops_cookbook/finops_prompt.md', please help me analyze
my project your-project-id, which has compute and storage in the US region.

Please list your plan before execution.
```

### Example Output

```markdown
### Current State
- Slot Metrics: p10=0.0, p25=0.0, p50=0.0, p95=1.4, max=190.7, avg=2.7
- Variability: CV=7.52 (Highly Variable)
- Burstiness: Ratio=Infinite (High burst)
- Top Project: your-project-id (387 slot-hours)
- Peak Hours: Day 2 (2:00-4:00), Day 7 (18:00-20:00)

### Recommended Strategy
Choice: Stay On-Demand (PAYG)

Reasoning: Workload shows very low average usage (2.7 slots) with extremely
high variability (CV > 7.0). Usage is sporadic with long idle periods followed
by short bursts. On-demand model provides optimal flexibility for this pattern.

### Implementation Steps
1. Continue current operations (no changes needed)
2. Monitor slot utilization patterns
3. Re-run analysis quarterly to detect pattern changes
```

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

## Best Practices

### When to Re-Run Analysis

- **Quarterly:** Regular check-ins for stable workloads
- **Monthly:** For rapidly growing or changing workloads
- **After Major Changes:** New projects, data migrations, architecture changes
- **Performance Issues:** Query slowdowns, slot contention, or failures
- **Capacity Planning:** Before committing to reservations or changing capacity

### Common Pitfalls to Avoid

1. **Committing Too Early**
   - Don't commit based on a single peak week
   - Analyze at least 30 days of data
   - Account for seasonal variations

2. **Ignoring Growth Trends**
   - Review week-over-week trends
   - Plan for expected growth
   - Leave headroom for expansion

3. **Over-Optimizing**
   - Don't chase 100% utilization
   - Target 70-85% for healthy buffer
   - Allow room for unexpected spikes

4. **Forgetting to Monitor**
   - Set up ongoing monitoring queries
   - Create alerts for utilization thresholds
   - Review quarterly at minimum

5. **Mixing Workload Types**
   - Separate production from dev/test
   - Use hybrid approach for mixed environments
   - Don't assign variable workloads to commitments

## Troubleshooting

### Common Errors and Solutions

**Error: "Access Denied" on INFORMATION_SCHEMA queries**

Solution: Ensure you have `roles/bigquery.resourceViewer` role:
```bash
gcloud projects add-iam-policy-binding [PROJECT_ID] \
  --member="user:[YOUR_EMAIL]" \
  --role="roles/bigquery.resourceViewer"
```

**Error: "Table not found: INFORMATION_SCHEMA.JOBS_TIMELINE_BY_PROJECT"**

Solution: Verify region qualifier is correct:
- Use `` `region-us` `` for multi-region US
- Use `` `region-eu` `` for multi-region EU
- Use `` `region-asia-northeast1` `` for specific regions

**Error: "Query returned 0 rows" for all queries**

Solution: Check data availability:
```sql
-- Verify jobs exist in the time range
SELECT COUNT(*) as job_count
FROM `region-us`.INFORMATION_SCHEMA.JOBS_BY_PROJECT
WHERE creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
```

**Error: "Division by zero" in metric calculations**

Solution: This indicates zero or near-zero usage. The workload is likely:
- Very new with minimal history
- Inactive or rarely used
- Better suited for on-demand billing

### Permission Requirements

Minimum required permissions:
- `bigquery.jobs.list`
- `bigquery.jobs.get`
- `bigquery.reservations.list`
- `bigquery.reservations.get`
- `bigquery.capacityCommitments.list`

Recommended role: `roles/bigquery.resourceViewer`

### Data Availability Issues

**INFORMATION_SCHEMA retention:**
- `JOBS_BY_PROJECT`: 180 days
- `JOBS_TIMELINE_BY_PROJECT`: 180 days
- `RESERVATIONS_BY_PROJECT`: Current state only

**Best practices:**
- Export historical data for long-term analysis
- Run analysis before data ages out
- Archive reports for trend comparison

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

### Support
For issues or questions:
1. Review the troubleshooting section above
2. Check official Google Cloud documentation
3. Consult with your organization's FinOps or data platform team
