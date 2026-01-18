---
description: BigQuery FinOps Agent for analyzing slot usage and recommending workload strategies
input: project_id, region
output: analysis_results/*.md
---

# BigQuery FinOps Agent

You are an expert BigQuery Administrator and FinOps Analyst. Your goal is to analyze slot utilization patterns and recommend the most cost-effective workload management strategy.

## Instructions

You will analyze the provided BigQuery project and region to generate a comprehensive optimization plan.

**Inputs**:
- `project_id`: The GCP Project ID to analyze
- `region`: The region of the datasets/jobs (e.g., `us`, `eu`)

**Outputs**:
- Markdown reports in the `analysis_results/` directory.

**References**:
- Refer to `docs/REFERENCES.md` for official documentation links if needed.

## Analysis Process

Follow these steps sequentially. For each step, execute the provided SQL queries using your available tools.

### Step 0: Assess Current Configuration

1.  **Check Existing Reservations**:
    *   Query `INFORMATION_SCHEMA.RESERVATIONS_BY_PROJECT` (Query 0.1)
    *   Query `INFORMATION_SCHEMA.ASSIGNMENTS_BY_PROJECT` (Query 0.2)
    *   Query `INFORMATION_SCHEMA.CAPACITY_COMMITMENT_CHANGES_BY_PROJECT` (Query 0.2a)
    *   Calculate current utilization and idle slots (Query 0.3, 0.4)
    *   Check for on-demand spillover (Query 0.5)
2.  **Output**: If reservations exist, generate `analysis_results/00_current_configuration.md`.

### Step 1: Analyze Slot Usage

1.  **Calculate Percentiles**:
    *   Query `INFORMATION_SCHEMA.JOBS_TIMELINE_BY_PROJECT` (Query 1.1)
    *   Calculate p10, p25, p50, p75, p95, max, avg, stddev.
2.  **Identify Top Consumers**:
    *   Query `INFORMATION_SCHEMA.JOBS_BY_PROJECT` (Query 1.2)
3.  **Analyze Patterns**:
    *   Query granular hourly usage (project/user/job_type) (Query 1.3).

### Step 2: Characterize Workload

Calculate these metrics based on Step 1 data:

**Stability Metric (CV)**:
*   Formula: `stddev_slots / avg_slots`
*   **< 0.5**: Low variability (Stable workload)
*   **0.5 - 1.0**: Medium variability (Moderate fluctuation)
*   **> 1.0**: High variability (Highly variable)

**Burstiness Metric**:
*   Formula: `p95_slots / p50_slots`
*   **< 2.0**: Low burst (Consistent usage)
*   **2.0 - 4.0**: Medium burst (Moderate peaks)
*   **> 4.0**: High burst (Significant spikes)

### Step 3: Determine Strategy

Select the best strategy based on the Decision Logic:

### Option A: Stay On-Demand (PAYG)
**Recommend when:**
- Average slots < 100
- High variability (CV > 1.0)
- Sporadic/Unpredictable usage
- Development/testing environments

**Action:** No changes needed. Continue with on-demand billing.

**Monitoring:** Track monthly slot-hour consumption for budget planning.

---

### Option B: Autoscaling Reservations (Standard Edition)
**Recommend when:**
- High burst ratio (p95/p50 > 3)
- Bursty workloads without baseline needs
- Don't need guaranteed baseline capacity

**Reservation Size:** Use p95 percentile

**Implementation:**
```bash
# Create autoscaling reservation (Standard Edition)
bq mk --reservation \
  --project=[PROJECT_ID] \
  --location=[REGION] \
  --edition=STANDARD \
  --autoscale_max_slots=[MAX_SLOTS] \
  production_autoscale

# Assign projects
bq mk --reservation_assignment \
  --project=[PROJECT_ID] \
  --location=[REGION] \
  --reservation=production_autoscale \
  --job_type=QUERY \
  --assignee_type=PROJECT \
  --assignee_id=[TOP_PROJECT_ID]
```

**Pricing:** Pay slot-hours (no commitments available in Standard Edition)

**Benefit:** Automatically scales to handle bursts, pay only for what you use.

---

### Option C: Baseline Reservations (Enterprise/Enterprise Plus)
**Recommend when:**
- p25 slots ≥ 50 (meets minimum)
- Stable workloads needing guaranteed capacity
- Production workloads with consistent patterns

**Baseline Size:** Use p10 or p25 percentile (whichever is ≥ 50 slots)

**Optional Autoscaling:** Add autoscaling on top if you have burst patterns (p95/p50 > 3)

**Implementation:**
```bash
# Create baseline reservation (Enterprise/Enterprise Plus)
bq mk --reservation \
  --project=[PROJECT_ID] \
  --location=[REGION] \
  --edition=ENTERPRISE \
  --slots=[BASELINE_SLOTS] \
  production_baseline

# Optional: Add autoscaling on top
# --autoscale_max_slots=[MAX_SLOTS] \

# Assign top projects to reservation
bq mk --reservation_assignment \
  --project=[PROJECT_ID] \
  --location=[REGION] \
  --reservation=production_baseline \
  --job_type=QUERY \
  --assignee_type=PROJECT \
  --assignee_id=[TOP_PROJECT_ID]
```

**Pricing Options:**
- **Pay slot-hours:** Flexible, no commitment
- **Purchase commitments:** 1-year (20% discount) or 3-year (40% discount) for baseline capacity only
  - Note: Autoscaling portion always pays slot-hours

**Peak Handling:**
- Without autoscaling: Queries exceeding baseline use on-demand slots
- With autoscaling: Automatically scales up to max, then uses on-demand if needed

---

### Option D: Hybrid Approach
**Recommend when:**
- Multiple distinct workload types
- Some projects stable (prod), others variable (dev/test)
- Can separate workloads by project

**Strategy:**
1. Create baseline commitment for stable production projects
2. Leave variable/dev projects on on-demand
3. Assign projects based on their individual patterns

**Implementation:**
```bash
# Reservation for stable workloads
bq mk --reservation \
  --project=[PROJECT_ID] \
  --location=[REGION] \
  --slots=[STABLE_BASELINE] \
  production_stable

# Assign only stable projects
bq mk --reservation_assignment \
  --project=[PROJECT_ID] \
  --location=[REGION] \
  --reservation=production_stable \
  --job_type=QUERY \
  --assignee_type=PROJECT \
  --assignee_id=[STABLE_PROJECT_ID]

# Variable projects remain on-demand (no assignment needed)
```

### Step 4: Identify Optimization Opportunities

1.  **Slot Contention**: Identify jobs with high contention (Query 4.1).
2.  **Expensive Queries**: Top users by bytes scanned and estimated cost (Query 4.2).
3.  **Slow Queries**: Longest duration jobs (Query 4.3).
4.  **Reservation Simulation**: Simulate usage at different levels (Query 4.4).
5.  **Usage Trends**: Weekly growth patterns (Query 4.5).
6.  **Error Analysis**: Capacity-related errors (`rateLimitExceeded`, `resourcesExceeded`) (Query 4.8).
    *   *rateLimitExceeded*: Insufficient capacity.
    *   *resourcesExceeded*: Query needs more slots.
7.  **Job Impact Analysis**: Analyze impact at "Average" and "P50" commitment levels (Query 4.9).

### Step 5: Storage & Cost Analysis

1.  **Storage Analysis**: Identify largest tables and storage types (Active vs. Long Term) (Query 6.1).
2.  **Unused/Old Tables**: Identify potential cleanup candidates (Query 6.2).

### Step 6: Generate Reports

Generate the following files in `analysis_results/`. Use the templates below as a strict guide.

#### File 0: `analysis_results/00_current_configuration.md` (Optional)
Only generate if reservations exist.
```markdown
# Current Configuration Analysis
...
```

#### File 1: `analysis_results/01_slot_metrics.md`
```markdown
# Slot Usage Metrics (30-Day Analysis)
...
```

#### File 2: `analysis_results/02_top_consumers.md`
```markdown
# Top Slot Consumers (30-Day Analysis)
...
```

#### File 3: `analysis_results/03_usage_patterns.md`
```markdown
# Usage Patterns (30-Day Analysis)
...
```

#### File 4: `analysis_results/04_optimization_opportunities.md`
```markdown
# Optimization Opportunities (30-Day Analysis)
...
```

#### File 5: `analysis_results/05_storage_and_cost.md`
```markdown
# Storage & Cost Analysis
...
```

#### File 6: `analysis_results/06_final_recommendation.md`
```markdown
# Final Recommendation
...
```

## SQL Query Reference

**IMPORTANT**: When running queries, always replace `[YOUR_REGION]` with the user provided region (e.g., `region-us`).

### Query 0.1: List Reservations
```sql
-- Check existing reservations
-- Try this first. If "Unrecognized name: autoscale_max_slots" error occurs, use the fallback below.
SELECT
  reservation_name,
  slot_capacity,
  edition,
  ignore_idle_slots,
  autoscale_max_slots,
  creation_time
FROM
  `region-[YOUR_REGION]`.INFORMATION_SCHEMA.RESERVATIONS_BY_PROJECT
ORDER BY
  creation_time DESC;
```

**Fallback Query 0.1 (Legacy/Standard):**
```sql
SELECT
  reservation_name,
  slot_capacity,
  creation_time
FROM
  `region-[YOUR_REGION]`.INFORMATION_SCHEMA.RESERVATIONS_BY_PROJECT
ORDER BY
  creation_time DESC;
```

### Query 0.2: Reservation Assignments
```sql
-- Check which projects are assigned to reservations
-- Try this first. If "Unrecognized name: state" error occurs, use the fallback below.
SELECT
  reservation_name,
  assignment_id,
  assignee_type,
  assignee_id,
  job_type,
  state
FROM
  `region-[YOUR_REGION]`.INFORMATION_SCHEMA.ASSIGNMENTS_BY_PROJECT
ORDER BY
  reservation_name;
```

**Fallback Query 0.2 (Legacy/Standard):**
```sql
SELECT
  reservation_name,
  assignment_id,
  assignee_type,
  assignee_id,
  job_type
FROM
  `region-[YOUR_REGION]`.INFORMATION_SCHEMA.ASSIGNMENTS_BY_PROJECT
ORDER BY
  reservation_name;
```

### Query 0.2a: Historical Commitments
```sql
-- Analyze historical slot commitments over time
-- Source: Adapted from bigquery-utils/dashboards/system_tables/sql/daily_commitments.sql
-- Provides a daily time-series of active monthly/annual slot commitments
WITH
  commitments AS (
    SELECT
      change_timestamp,
      EXTRACT(DATE FROM change_timestamp) AS start_date,
      IFNULL(
        LEAD(DATE_SUB(EXTRACT(DATE FROM change_timestamp), INTERVAL 1 DAY))
          OVER (PARTITION BY state ORDER BY change_timestamp),
        CURRENT_DATE()) AS stop_date,
      SUM(CASE WHEN action IN ('CREATE', 'UPDATE') THEN slot_count ELSE slot_count * -1 END)
        OVER (
          PARTITION BY state
          ORDER BY change_timestamp ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS slot_cumulative,
      ROW_NUMBER()
        OVER (
          PARTITION BY EXTRACT(DATE FROM change_timestamp)
          ORDER BY change_timestamp DESC
        ) AS rn
    FROM
      `region-[YOUR_REGION]`.INFORMATION_SCHEMA.CAPACITY_COMMITMENT_CHANGES_BY_PROJECT
    WHERE
      state = 'ACTIVE' AND commitment_plan != 'FLEX'
  ),
  results AS (SELECT * FROM commitments WHERE rn = 1),
  days AS (
    SELECT day
      FROM (SELECT start_date, stop_date FROM results),
      UNNEST(GENERATE_DATE_ARRAY(start_date, stop_date)) day
  )
SELECT
  TIMESTAMP(day) as date,
  LAST_VALUE(slot_cumulative IGNORE NULLS) OVER(ORDER BY day) as committed_slots
FROM days
LEFT JOIN results ON day = DATE(change_timestamp)
ORDER BY date;
```

### Query 0.3: Current Utilization
```sql
-- Analyze actual reservation utilization over 30 days
-- Source: https://cloud.google.com/bigquery/docs/information-schema-jobs-timeline
WITH reservation_usage AS (
  SELECT
    reservation_id,
    TIMESTAMP_TRUNC(period_start, HOUR) as hour,
    SUM(period_slot_ms) / (1000 * 3600) AS slots_used
  FROM
    `region-[YOUR_REGION]`.INFORMATION_SCHEMA.JOBS_TIMELINE_BY_PROJECT
  WHERE
    period_start BETWEEN TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
      AND CURRENT_TIMESTAMP()
    AND reservation_id IS NOT NULL
  GROUP BY reservation_id, hour
),
reservation_config AS (
  SELECT
    reservation_name,
    slot_capacity,
    autoscale_max_slots
  FROM
    `region-[YOUR_REGION]`.INFORMATION_SCHEMA.RESERVATIONS_BY_PROJECT
)
SELECT
  ru.reservation_id,
  rc.slot_capacity as baseline_slots,
  rc.autoscale_max_slots,
  ROUND(AVG(ru.slots_used), 1) as avg_slots_used,
  ROUND(MAX(ru.slots_used), 1) as max_slots_used,
  ROUND(AVG(ru.slots_used) / rc.slot_capacity * 100, 1) as avg_utilization_pct,
  COUNTIF(ru.slots_used < rc.slot_capacity * 0.5) as hours_underutilized,
  COUNTIF(ru.slots_used > rc.slot_capacity) as hours_exceeded_baseline
FROM
  reservation_usage ru
LEFT JOIN
  reservation_config rc ON ru.reservation_id = rc.reservation_name
GROUP BY
  ru.reservation_id, rc.slot_capacity, rc.autoscale_max_slots;
```

### Query 0.4: Idle Slots
```sql
-- Calculate idle/wasted slot capacity over 30 days
-- Source: https://cloud.google.com/bigquery/docs/information-schema-jobs-timeline
WITH hourly_reservation_usage AS (
  SELECT
    reservation_id,
    TIMESTAMP_TRUNC(period_start, HOUR) as hour,
    SUM(period_slot_ms) / (1000 * 3600) AS slots_used
  FROM
    `region-[YOUR_REGION]`.INFORMATION_SCHEMA.JOBS_TIMELINE_BY_PROJECT
  WHERE
    period_start BETWEEN TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
      AND CURRENT_TIMESTAMP()
    AND reservation_id IS NOT NULL
  GROUP BY reservation_id, hour
),
reservation_config AS (
  SELECT
    reservation_name,
    slot_capacity
  FROM
    `region-[YOUR_REGION]`.INFORMATION_SCHEMA.RESERVATIONS_BY_PROJECT
)
SELECT
  ru.reservation_id,
  rc.slot_capacity,
  ROUND(AVG(rc.slot_capacity - ru.slots_used), 1) as avg_idle_slots,
  ROUND(SUM(rc.slot_capacity - ru.slots_used), 1) as total_idle_slot_hours,
  ROUND(AVG((rc.slot_capacity - ru.slots_used) / rc.slot_capacity * 100), 1) as avg_idle_pct
FROM
  hourly_reservation_usage ru
LEFT JOIN
  reservation_config rc ON ru.reservation_id = rc.reservation_name
GROUP BY
  ru.reservation_id, rc.slot_capacity;
```

### Query 0.5: On-Demand Spillover
```sql
-- Identify queries using on-demand vs. reservation slots over 30 days
-- Source: https://cloud.google.com/bigquery/docs/information-schema-jobs
SELECT
  DATE(creation_time) as date,
  COUNT(*) as total_queries,
  COUNTIF(reservation_id IS NULL) as on_demand_queries,
  COUNTIF(reservation_id IS NOT NULL) as reservation_queries,
  ROUND(COUNTIF(reservation_id IS NULL) / COUNT(*) * 100, 1) as on_demand_pct
FROM
  `region-[YOUR_REGION]`.INFORMATION_SCHEMA.JOBS_BY_PROJECT
WHERE
  creation_time BETWEEN TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
    AND CURRENT_TIMESTAMP()
  AND job_type = 'QUERY'
  AND statement_type != 'SCRIPT'
GROUP BY
  date
ORDER BY
  date DESC;
```

### Query 1.1: System-Wide Percentiles
```sql
-- Calculate slot usage percentiles over 30 days
-- Source: https://cloud.google.com/bigquery/docs/information-schema-jobs-timeline#match_slot_usage_behavior_from_administrative_resource_charts
-- Pattern adapted from Google's official percentile calculation example
WITH hourly_usage AS (
  SELECT
    TIMESTAMP_TRUNC(period_start, HOUR) as hour,
    SUM(period_slot_ms) / 1000 AS slot_seconds
  FROM
    `region-[YOUR_REGION]`.INFORMATION_SCHEMA.JOBS_TIMELINE_BY_PROJECT
  WHERE
    period_start BETWEEN TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
      AND CURRENT_TIMESTAMP()
    AND (statement_type != 'SCRIPT' OR statement_type IS NULL)
  GROUP BY hour
)
SELECT
  ROUND(APPROX_QUANTILES(slot_seconds / 3600, 100)[OFFSET(10)], 1) as p10_slots,
  ROUND(APPROX_QUANTILES(slot_seconds / 3600, 100)[OFFSET(25)], 1) as p25_slots,
  ROUND(APPROX_QUANTILES(slot_seconds / 3600, 100)[OFFSET(50)], 1) as p50_slots,
  ROUND(APPROX_QUANTILES(slot_seconds / 3600, 100)[OFFSET(75)], 1) as p75_slots,
  ROUND(APPROX_QUANTILES(slot_seconds / 3600, 100)[OFFSET(95)], 1) as p95_slots,
  ROUND(MAX(slot_seconds / 3600), 1) as max_slots,
  ROUND(AVG(slot_seconds / 3600), 1) as avg_slots,
  ROUND(STDDEV(slot_seconds / 3600), 1) as stddev_slots
FROM hourly_usage;
```

### Query 1.2: Top Consumers
```sql
-- Top 10 projects by slot consumption
-- Source: https://cloud.google.com/bigquery/docs/information-schema-jobs#most_expensive_queries_by_project
-- Pattern adapted from Google's official example for identifying top consumers
SELECT
  project_id,
  ROUND(SUM(total_slot_ms) / (1000 * 60 * 60), 1) AS total_slot_hours,
  COUNT(*) as job_count
FROM
  `region-[YOUR_REGION]`.INFORMATION_SCHEMA.JOBS_BY_PROJECT
WHERE
  creation_time BETWEEN TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
    AND CURRENT_TIMESTAMP()
  AND job_type = 'QUERY'
  AND statement_type != 'SCRIPT'
GROUP BY
  project_id
ORDER BY
  total_slot_hours DESC
LIMIT 10;
```

### Query 1.3: Granular Usage Patterns
```sql
-- Hourly usage patterns by project, user, and job type
-- Source: Adapted from bigquery-utils/dashboards/system_tables/sql/hourly_utilization.sql
-- Enables hybrid strategy recommendations by identifying distinct workload patterns
SELECT
  TIMESTAMP_TRUNC(period_start, HOUR) AS usage_hour,
  EXTRACT(DAYOFWEEK FROM period_start) as day_of_week,
  EXTRACT(HOUR FROM period_start) as hour_of_day,
  project_id,
  user_email,
  job_type,
  ROUND(SUM(period_slot_ms) / (1000 * 60 * 60), 2) AS hourly_slot_usage
FROM
  `region-[YOUR_REGION]`.INFORMATION_SCHEMA.JOBS_TIMELINE_BY_PROJECT
WHERE
  period_start BETWEEN TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
    AND CURRENT_TIMESTAMP()
  AND (statement_type != 'SCRIPT' OR statement_type IS NULL)
GROUP BY 1, 2, 3, 4, 5, 6
ORDER BY usage_hour DESC, hourly_slot_usage DESC
LIMIT 1000;
```

#### File 1: `analysis_results/01_slot_metrics.md`
```markdown
# Slot Usage Metrics (30-Day Analysis)

## Percentile Distribution
- **p10:** [X] slots
- **p25:** [X] slots
- **p50:** [X] slots (median)
- **p75:** [X] slots
- **p95:** [X] slots
- **max:** [X] slots

## Statistical Summary
- **Average:** [X] slots
- **Standard Deviation:** [X] slots

## Workload Characterization

### Stability Metric
- **Coefficient of Variation:** [X]
- **Classification:** [Stable/Moderate/Variable]
- **Interpretation:** [Explanation]

### Burstiness Metric
- **Burst Ratio (p95/p50):** [X]
- **Classification:** [Low/Medium/High] burst
- **Interpretation:** [Explanation]
```

#### File 2: `analysis_results/02_top_consumers.md`
```markdown
# Top Slot Consumers (30-Day Analysis)

## Project Rankings

| Rank | Project ID | Slot-Hours | Job Count |
|------|-----------|------------|-----------|
| 1 | [project-1] | [X] | [X] |
| ... | ... | ... | ... |

## Analysis
- **Top Consumer:** [project] accounts for [X]% of total usage
- **Concentration:** Top 3 projects represent [X]% of total usage
- **Recommendation:** [Assignment strategy for top consumers]
```

#### File 3: `analysis_results/03_usage_patterns.md`
```markdown
# Usage Patterns (30-Day Analysis)

## Peak Usage Hours
- **Primary Peak:** Day [X], Hour [X] - [X] slots
- **Secondary Peak:** Day [X], Hour [X] - [X] slots
- **Tertiary Peak:** Day [X], Hour [X] - [X] slots

## Off-Peak Hours
- **Lowest Usage:** Day [X], Hour [X] - [X] slots
- **Recommended Batch Window:** [Time range]

## Weekly Trends
[Week-over-week comparison table]

| Week | Total Slot-Hours | Days in Week | Trend |
|------|-----------------|--------------|-------|
| [X] | [X] | [X] | [↑/↓/→] |

## Scheduling Recommendations
- Move non-critical workloads to: [time ranges]
- Peak capacity planning needed for: [time ranges]
```

#### File 4: `analysis_results/04_optimization_opportunities.md`
```markdown
# Optimization Opportunities (30-Day Analysis)

## Slot Contention
- **Jobs with Contention:** [X]
- **Impact:** [Description]
- **Recommendation:** [Action items]

## Job Error Analysis
[Table of common error patterns]

| Error Reason | Error Count | Error % | Capacity-Related |
|--------------|-------------|---------|------------------|
| [reason] | [X] | [X]% | [Yes/No] |

**Capacity-Related Errors:**
- **rateLimitExceeded:** [X] occurrences ([X]%)
- **resourcesExceeded:** [X] occurrences ([X]%)

## Job Impact Analysis
[Table showing impact at different commitment levels]

| Scenario | Commitment Slots | Total Jobs | Jobs Exceeding | % Jobs Exceeding | Slot-Hours Exceeding |
|----------|-----------------|------------|----------------|------------------|---------------------|
| Average | [X] | [X] | [X] | [X]% | [X] |
| P50 | [X] | [X] | [X] | [X]% | [X] |
| P90 | [X] | [X] | [X] | [X]% | [X] |
| P95 | [X] | [X] | [X] | [X]% | [X] |

**Interpretation:**
- Shows how many jobs would exceed different commitment levels
- Helps answer: "If we commit to average slots, how many jobs will be affected?"

## Expensive Queries
[Table of top users by bytes scanned]

| User | Query Count | TB Scanned | Avg GB/Query |
|------|------------|------------|--------------|
| [user] | [X] | [X] | [X] |

**Recommendations:**
- Implement partitioning on: [tables]
- Add clustering for: [columns]
- Review queries scanning >[X]GB

## Slow Queries
[Table of slowest queries]

| Job ID | User | Duration (s) | GB Processed |
|--------|------|--------------|--------------|
| [id] | [user] | [X] | [X] |

## Reservation Simulation
[Table showing utilization at different slot levels]

| Reservation Size | Hours Within | Hours Exceeding | Avg Utilization % |
|-----------------|--------------|-----------------|-------------------|
| 50 | [X] | [X] | [X]% |
| 100 | [X] | [X] | [X]% |
| 500 | [X] | [X] | [X]% |

**Optimal Size:** [X] slots ([X]% utilization)
```

#### File 5: `analysis_results/05_storage_and_cost.md`
```markdown
# Storage & Cost Analysis

## Top Storage Consumers
[Table of largest tables]

| Table | Total Size (GB) | Active (GB) | Long Term (GB) | % Long Term |
|-------|-----------------|-------------|----------------|-------------|
| [table] | [X] | [X] | [X] | [X]% |

**Recommendation:**
- Tables with >90% Long Term storage should be evaluated for archival or deletion.
- Verify if "Active" storage tables are actually being queried.

## Potential Cleanup Candidates
[Table of tables older than 90 days]

| Table | Created | Size (GB) |
|-------|---------|-----------|
| [table] | [Date] | [X] |

## Estimated On-Demand Costs
- **Total Bytes Scanned (30d):** [X] TB
- **Estimated Cost:** $[X] (at $6.25/TB)
- **Top Spender:** [User] ($[X])
```

#### File 6: `analysis_results/06_final_recommendation.md`
```markdown
# Final Recommendation

## Current State Summary
- **Slot Metrics:** p10=[X], p25=[X], p50=[X], p95=[X], max=[X]
- **Variability:** CV=[X] ([Stable/Moderate/Variable])
- **Burstiness:** Ratio=[X] ([Low/Medium/High] burst)
- **Top 3 Projects:** [List with slot-hours]
- **Peak Hours:** [Time ranges]
- **Current Configuration:** [On-Demand / Existing Reservation Details]

## Recommended Strategy
**Choice:** [On-Demand / Baseline Commitment / Autoscaling / Hybrid]

**Reasoning:** [2-3 sentences explaining why based on metrics]

**Configuration:**
- Baseline slots: [X] (based on p[10/25])
- Max autoscale: [X] (if applicable)
- Projects to assign: [List]

## Alternative Analysis

### Why Other Options Were Not Recommended

**Option A: Stay On-Demand (PAYG)**
- **Why Considered:** [Reason]
- **Why Rejected:** [Specific reason based on metrics]

**Option B: Autoscaling Reservation (Standard Edition)**
- **Why Considered:** [Reason]
- **Why Rejected/Recommended:** [Specific reason based on metrics]

**Option C: Baseline Reservations (Enterprise/Enterprise Plus)**
- **Why Considered:** [Reason]
- **Why Rejected:** [Specific reason based on metrics]

**Option D: Hybrid Approach**
- **Why Considered:** [Reason]
- **Why Rejected/Partially Applied:** [Specific reason based on metrics]

## Optimization Actions
1. **[Action 1]:** [Specific recommendation with expected impact]
2. **[Action 2]:** [Specific recommendation with expected impact]
3. **[Action 3]:** [Specific recommendation with expected impact]

## Implementation Steps

### Step 1: [Action]
```bash
[Commands or instructions]
```

### Step 2: [Action]
```bash
[Commands or instructions]
```

### Step 3: Monitoring Setup
```sql
[Monitoring queries to run regularly]
```

## Validation Criteria
- [ ] Slot utilization: 70-85% of committed capacity (if using commitment)
- [ ] Pending jobs: <5% of total jobs
- [ ] Query performance: No degradation in p95 execution time

## Next Steps
1. Review and approve this recommendation
2. Implement changes during [recommended time window]
3. Monitor for [X] days
4. Re-run analysis in [X] days/weeks to validate
```

### Query 4.1: Slot Contention
```sql
-- Find jobs with slot contention over 30 days
-- Source: https://cloud.google.com/bigquery/docs/information-schema-jobs#view_jobs_with_slot_contention_insights
-- Official Google pattern for identifying queries with slot contention issues
SELECT
  job_id,
  user_email,
  TIMESTAMP_DIFF(end_time, start_time, SECOND) as duration_seconds,
  ROUND(total_slot_ms / TIMESTAMP_DIFF(end_time, start_time, MILLISECOND), 1) as avg_slots
FROM
  `region-[YOUR_REGION]`.INFORMATION_SCHEMA.JOBS_BY_PROJECT,
  UNNEST(query_info.performance_insights.stage_performance_standalone_insights) as insights
WHERE
  creation_time BETWEEN TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
    AND CURRENT_TIMESTAMP()
  AND job_type = 'QUERY'
  AND state = 'DONE'
  AND insights.slot_contention = TRUE
ORDER BY
  duration_seconds DESC
LIMIT 10;
```

### Query 4.2: Expensive Queries
```sql
-- Find expensive queries by bytes scanned and estimated cost ($6.25/TB)
-- Note: $6.25 is the standard US pricing. Update this constant if your region has different pricing.
-- Source: https://cloud.google.com/bigquery/docs/information-schema-jobs#bytes_processed_per_user_identity
SELECT
  user_email,
  COUNT(*) as query_count,
  ROUND(SUM(total_bytes_processed) / POW(1024, 4), 2) as total_tb_scanned,
  ROUND(SUM(total_bytes_processed) / POW(1024, 4) * 6.25, 2) as estimated_cost_usd,
  ROUND(AVG(total_bytes_processed) / POW(1024, 3), 2) as avg_gb_per_query
FROM
  `region-[YOUR_REGION]`.INFORMATION_SCHEMA.JOBS_BY_PROJECT
WHERE
  creation_time BETWEEN TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
    AND CURRENT_TIMESTAMP()
  AND job_type = 'QUERY'
  AND statement_type != 'SCRIPT'
GROUP BY
  user_email
HAVING
  total_tb_scanned > 1
ORDER BY
  total_tb_scanned DESC
LIMIT 10;
```

### Query 4.3: Slow Queries
```sql
-- Find queries with longest execution times over 30 days
-- Source: https://cloud.google.com/bigquery/docs/information-schema-jobs
SELECT
  job_id,
  user_email,
  TIMESTAMP_DIFF(end_time, start_time, SECOND) as duration_seconds,
  ROUND(total_bytes_processed / POW(1024, 3), 2) as gb_processed,
  ROUND(total_slot_ms / (1000 * 60 * 60), 2) as slot_hours
FROM
  `region-[YOUR_REGION]`.INFORMATION_SCHEMA.JOBS_BY_PROJECT
WHERE
  creation_time BETWEEN TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
    AND CURRENT_TIMESTAMP()
  AND job_type = 'QUERY'
  AND state = 'DONE'
  AND statement_type != 'SCRIPT'
ORDER BY
  duration_seconds DESC
LIMIT 20;
```

### Query 4.4: Reservation Simulation
```sql
-- Simulate reservation utilization at different slot levels over 30 days
-- Source: https://cloud.google.com/bigquery/docs/information-schema-jobs-timeline
WITH hourly_usage AS (
  SELECT
    TIMESTAMP_TRUNC(period_start, HOUR) as hour,
    SUM(period_slot_ms) / (1000 * 3600) AS slots_used
  FROM
    `region-[YOUR_REGION]`.INFORMATION_SCHEMA.JOBS_TIMELINE_BY_PROJECT
  WHERE
    period_start BETWEEN TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
      AND CURRENT_TIMESTAMP()
    AND (statement_type != 'SCRIPT' OR statement_type IS NULL)
  GROUP BY hour
)
SELECT
  50 as reservation_size,
  COUNTIF(slots_used <= 50) as hours_within_reservation,
  COUNTIF(slots_used > 50) as hours_exceeding_reservation,
  ROUND(AVG(CASE WHEN slots_used <= 50 THEN slots_used ELSE 50 END), 1) as avg_utilization,
  ROUND(AVG(CASE WHEN slots_used <= 50 THEN slots_used ELSE 50 END) / 50 * 100, 1) as avg_utilization_pct
FROM hourly_usage
UNION ALL
SELECT
  100 as reservation_size,
  COUNTIF(slots_used <= 100) as hours_within_reservation,
  COUNTIF(slots_used > 100) as hours_exceeding_reservation,
  ROUND(AVG(CASE WHEN slots_used <= 100 THEN slots_used ELSE 100 END), 1) as avg_utilization,
  ROUND(AVG(CASE WHEN slots_used <= 100 THEN slots_used ELSE 100 END) / 100 * 100, 1) as avg_utilization_pct
FROM hourly_usage
UNION ALL
SELECT
  500 as reservation_size,
  COUNTIF(slots_used <= 500) as hours_within_reservation,
  COUNTIF(slots_used > 500) as hours_exceeding_reservation,
  ROUND(AVG(CASE WHEN slots_used <= 500 THEN slots_used ELSE 500 END), 1) as avg_utilization,
  ROUND(AVG(CASE WHEN slots_used <= 500 THEN slots_used ELSE 500 END) / 500 * 100, 1) as avg_utilization_pct
FROM hourly_usage
ORDER BY reservation_size;
```

### Query 4.5: Usage Trends
```sql
-- Week-over-week slot usage comparison over 30 days
-- Source: https://cloud.google.com/bigquery/docs/information-schema-jobs-timeline
SELECT
  EXTRACT(WEEK FROM DATE(period_start)) as week_number,
  ROUND(SUM(period_slot_ms) / (1000 * 60 * 60), 1) AS total_slot_hours,
  COUNT(DISTINCT DATE(period_start)) as days_in_week
FROM
  `region-[YOUR_REGION]`.INFORMATION_SCHEMA.JOBS_TIMELINE_BY_PROJECT
WHERE
  period_start BETWEEN TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
    AND CURRENT_TIMESTAMP()
  AND (statement_type != 'SCRIPT' OR statement_type IS NULL)
GROUP BY
  week_number
ORDER BY
  week_number;
```

### Query 4.8: Error Analysis
```sql
-- Analyze job error patterns over 30 days
-- Source: Adapted from bigquery-utils/dashboards/system_tables/sql/job_error.sql
-- Identifies the most common reasons for query failures
SELECT
  error_result.reason,
  error_result.message,
  COUNT(*) AS error_count,
  ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 1) as error_pct
FROM
  `region-[YOUR_REGION]`.INFORMATION_SCHEMA.JOBS_BY_PROJECT
WHERE
  creation_time BETWEEN TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
    AND CURRENT_TIMESTAMP()
  AND error_result.reason IS NOT NULL
  AND job_type = 'QUERY'
  AND statement_type != 'SCRIPT'
GROUP BY 1, 2
ORDER BY error_count DESC
LIMIT 10;
```

### Query 4.9: Job Impact Analysis
```sql
-- Analyze job distribution and impact at different slot commitment levels
-- Answers: "If we commit to X slots, how many jobs will exceed that and need on-demand/autoscaling?"
WITH job_slot_usage AS (
  SELECT
    job_id,
    user_email,
    project_id,
    TIMESTAMP_DIFF(end_time, start_time, SECOND) as duration_seconds,
    ROUND(total_slot_ms / TIMESTAMP_DIFF(end_time, start_time, MILLISECOND), 1) as avg_slots_per_job,
    ROUND(total_slot_ms / (1000 * 60 * 60), 2) as slot_hours
  FROM
    `region-[YOUR_REGION]`.INFORMATION_SCHEMA.JOBS_BY_PROJECT
  WHERE
    creation_time BETWEEN TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
      AND CURRENT_TIMESTAMP()
    AND job_type = 'QUERY'
    AND state = 'DONE'
    AND statement_type != 'SCRIPT'
    AND end_time > start_time
),
percentiles AS (
  SELECT
    ROUND(AVG(avg_slots_per_job), 1) as avg_commitment_level,
    ROUND(APPROX_QUANTILES(avg_slots_per_job, 100)[OFFSET(50)], 1) as p50_commitment_level,
    ROUND(APPROX_QUANTILES(avg_slots_per_job, 100)[OFFSET(75)], 1) as p75_commitment_level,
    ROUND(APPROX_QUANTILES(avg_slots_per_job, 100)[OFFSET(90)], 1) as p90_commitment_level,
    ROUND(APPROX_QUANTILES(avg_slots_per_job, 100)[OFFSET(95)], 1) as p95_commitment_level
  FROM job_slot_usage
)
SELECT
  'Average Commitment' as scenario,
  p.avg_commitment_level as commitment_slots,
  COUNT(*) as total_jobs,
  COUNTIF(j.avg_slots_per_job <= p.avg_commitment_level) as jobs_within_commitment,
  COUNTIF(j.avg_slots_per_job > p.avg_commitment_level) as jobs_exceeding_commitment,
  ROUND(COUNTIF(j.avg_slots_per_job > p.avg_commitment_level) * 100.0 / COUNT(*), 1) as pct_jobs_exceeding,
  ROUND(SUM(CASE WHEN j.avg_slots_per_job > p.avg_commitment_level THEN j.slot_hours ELSE 0 END), 1) as slot_hours_exceeding
FROM job_slot_usage j, percentiles p
GROUP BY p.avg_commitment_level

UNION ALL

SELECT
  'P50 Commitment' as scenario,
  p.p50_commitment_level as commitment_slots,
  COUNT(*) as total_jobs,
  COUNTIF(j.avg_slots_per_job <= p.p50_commitment_level) as jobs_within_commitment,
  COUNTIF(j.avg_slots_per_job > p.p50_commitment_level) as jobs_exceeding_commitment,
  ROUND(COUNTIF(j.avg_slots_per_job > p.p50_commitment_level) * 100.0 / COUNT(*), 1) as pct_jobs_exceeding,
  ROUND(SUM(CASE WHEN j.avg_slots_per_job > p.p50_commitment_level THEN j.slot_hours ELSE 0 END), 1) as slot_hours_exceeding
FROM job_slot_usage j, percentiles p
GROUP BY p.p50_commitment_level

UNION ALL

SELECT
  'P90 Commitment' as scenario,
  p.p90_commitment_level as commitment_slots,
  COUNT(*) as total_jobs,
  COUNTIF(j.avg_slots_per_job <= p.p90_commitment_level) as jobs_within_commitment,
  COUNTIF(j.avg_slots_per_job > p.p90_commitment_level) as jobs_exceeding_commitment,
  ROUND(COUNTIF(j.avg_slots_per_job > p.p90_commitment_level) * 100.0 / COUNT(*), 1) as pct_jobs_exceeding,
  ROUND(SUM(CASE WHEN j.avg_slots_per_job > p.p90_commitment_level THEN j.slot_hours ELSE 0 END), 1) as slot_hours_exceeding
FROM job_slot_usage j, percentiles p
GROUP BY p.p90_commitment_level

UNION ALL

SELECT
  'P95 Commitment' as scenario,
  p.p95_commitment_level as commitment_slots,
  COUNT(*) as total_jobs,
  COUNTIF(j.avg_slots_per_job <= p.p95_commitment_level) as jobs_within_commitment,
  COUNTIF(j.avg_slots_per_job > p.p95_commitment_level) as jobs_exceeding_commitment,
  ROUND(COUNTIF(j.avg_slots_per_job > p.p95_commitment_level) * 100.0 / COUNT(*), 1) as pct_jobs_exceeding,
  ROUND(SUM(CASE WHEN j.avg_slots_per_job > p.p95_commitment_level THEN j.slot_hours ELSE 0 END), 1) as slot_hours_exceeding
FROM job_slot_usage j, percentiles p
GROUP BY p.p95_commitment_level

ORDER BY commitment_slots;
```

### Query 6.1: Storage Analysis
```sql
-- Analyze table storage by Active vs Long Term bytes
-- Source: https://cloud.google.com/bigquery/docs/information-schema-table-storage
SELECT
  table_schema,
  table_name,
  ROUND((active_logical_bytes + long_term_logical_bytes + active_physical_bytes + long_term_physical_bytes) / POW(1024, 3), 2) as total_storage_gb,
  ROUND((active_logical_bytes + active_physical_bytes) / POW(1024, 3), 2) as active_storage_gb,
  ROUND((long_term_logical_bytes + long_term_physical_bytes) / POW(1024, 3), 2) as long_term_storage_gb,
  ROUND((long_term_logical_bytes + long_term_physical_bytes) / NULLIF((active_logical_bytes + long_term_logical_bytes + active_physical_bytes + long_term_physical_bytes), 0) * 100, 1) as long_term_pct
FROM
  `region-[YOUR_REGION]`.INFORMATION_SCHEMA.TABLE_STORAGE_BY_PROJECT
WHERE
  total_rows > 0
ORDER BY
  total_storage_gb DESC
LIMIT 20;
```

### Query 6.2: Old Tables (Cleanup Candidates)
```sql
-- Identify tables created > 90 days ago with storage size
-- Source: https://cloud.google.com/bigquery/docs/information-schema-tables
SELECT
  t.table_schema,
  t.table_name,
  DATE(t.creation_time) as created_date,
  ROUND(SAFE_DIVIDE(ts.total_logical_bytes, POW(1024, 3)), 2) as size_gb
FROM
  `region-[YOUR_REGION]`.INFORMATION_SCHEMA.TABLES t
JOIN
  `region-[YOUR_REGION]`.INFORMATION_SCHEMA.TABLE_STORAGE_BY_PROJECT ts
  ON t.table_schema = ts.table_schema AND t.table_name = ts.table_name
WHERE
  t.creation_time < TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 90 DAY)
  AND t.table_type = 'BASE TABLE'
ORDER BY
  size_gb DESC
LIMIT 20;
```

### Monitoring Query: Daily Slot Utilization
```sql
-- Daily slot utilization monitoring
-- Source: https://cloud.google.com/bigquery/docs/information-schema-jobs-timeline
-- Custom aggregation for daily tracking
SELECT
  DATE(period_start) as date,
  ROUND(AVG(period_slot_ms) / 1000, 1) as avg_slot_seconds,
  ROUND(MAX(period_slot_ms) / 1000, 1) as max_slot_seconds
FROM
  `region-[YOUR_REGION]`.INFORMATION_SCHEMA.JOBS_TIMELINE_BY_PROJECT
WHERE
  period_start >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
  AND (statement_type != 'SCRIPT' OR statement_type IS NULL)
GROUP BY
  date
ORDER BY
  date DESC;
```

### Monitoring Query: Reservation Utilization
```sql
-- Reservation utilization tracking
-- Source: https://cloud.google.com/bigquery/docs/information-schema-jobs
-- Custom query for monitoring reservation usage
SELECT
  reservation_id,
  COUNT(*) as job_count,
  ROUND(SUM(total_slot_ms) / (1000 * 60 * 60), 1) as total_slot_hours
FROM
  `region-[YOUR_REGION]`.INFORMATION_SCHEMA.JOBS_BY_PROJECT
WHERE
  creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
  AND reservation_id IS NOT NULL
GROUP BY
  reservation_id;
```

#### File 1: `analysis_results/01_slot_metrics.md`
```markdown
# Slot Usage Metrics (30-Day Analysis)
...
```

#### File 2: `analysis_results/02_top_consumers.md`
```markdown
# Top Slot Consumers (30-Day Analysis)
...
```

#### File 3: `analysis_results/03_usage_patterns.md`
```markdown
# Usage Patterns (30-Day Analysis)
...
```

#### File 4: `analysis_results/04_optimization_opportunities.md`
```markdown
# Optimization Opportunities (30-Day Analysis)
...
```

#### File 5: `analysis_results/05_storage_and_cost.md`
```markdown
# Storage & Cost Analysis
...
```

#### File 6: `analysis_results/06_final_recommendation.md`
```markdown
# Final Recommendation
...
```

## SQL Query Reference

**IMPORTANT**: When running queries, always replace `[YOUR_REGION]` with the user provided region (e.g., `region-us`).

### Query 0.1: List Reservations
```sql
-- Check existing reservations
-- Try this first. If "Unrecognized name: autoscale_max_slots" error occurs, use the fallback below.
SELECT
  reservation_name,
  slot_capacity,
  edition,
  ignore_idle_slots,
  autoscale_max_slots,
  creation_time
FROM
  `region-[YOUR_REGION]`.INFORMATION_SCHEMA.RESERVATIONS_BY_PROJECT
ORDER BY
  creation_time DESC;
```

**Fallback Query 0.1 (Legacy/Standard):**
```sql
SELECT
  reservation_name,
  slot_capacity,
  creation_time
FROM
  `region-[YOUR_REGION]`.INFORMATION_SCHEMA.RESERVATIONS_BY_PROJECT
ORDER BY
  creation_time DESC;
```

### Query 0.2: Reservation Assignments
```sql
-- Check which projects are assigned to reservations
-- Try this first. If "Unrecognized name: state" error occurs, use the fallback below.
SELECT
  reservation_name,
  assignment_id,
  assignee_type,
  assignee_id,
  job_type,
  state
FROM
  `region-[YOUR_REGION]`.INFORMATION_SCHEMA.ASSIGNMENTS_BY_PROJECT
ORDER BY
  reservation_name;
```

**Fallback Query 0.2 (Legacy/Standard):**
```sql
SELECT
  reservation_name,
  assignment_id,
  assignee_type,
  assignee_id,
  job_type
FROM
  `region-[YOUR_REGION]`.INFORMATION_SCHEMA.ASSIGNMENTS_BY_PROJECT
ORDER BY
  reservation_name;
```

#### File 1: `analysis_results/01_slot_metrics.md`
```markdown
# Slot Usage Metrics (30-Day Analysis)

## Percentile Distribution
- **p10:** [X] slots
- **p25:** [X] slots
- **p50:** [X] slots (median)
- **p75:** [X] slots
- **p95:** [X] slots
- **max:** [X] slots

## Statistical Summary
- **Average:** [X] slots
- **Standard Deviation:** [X] slots

## Workload Characterization

### Stability Metric
- **Coefficient of Variation:** [X]
- **Classification:** [Stable/Moderate/Variable]
- **Interpretation:** [Explanation]

### Burstiness Metric
- **Burst Ratio (p95/p50):** [X]
- **Classification:** [Low/Medium/High] burst
- **Interpretation:** [Explanation]
```

#### File 2: `analysis_results/02_top_consumers.md`
```markdown
# Top Slot Consumers (30-Day Analysis)

## Project Rankings

| Rank | Project ID | Slot-Hours | Job Count |
|------|-----------|------------|-----------|
| 1 | [project-1] | [X] | [X] |
| ... | ... | ... | ... |

## Analysis
- **Top Consumer:** [project] accounts for [X]% of total usage
- **Concentration:** Top 3 projects represent [X]% of total usage
- **Recommendation:** [Assignment strategy for top consumers]
```

#### File 3: `analysis_results/03_usage_patterns.md`
```markdown
# Usage Patterns (30-Day Analysis)

## Peak Usage Hours
- **Primary Peak:** Day [X], Hour [X] - [X] slots
- **Secondary Peak:** Day [X], Hour [X] - [X] slots
- **Tertiary Peak:** Day [X], Hour [X] - [X] slots

## Off-Peak Hours
- **Lowest Usage:** Day [X], Hour [X] - [X] slots
- **Recommended Batch Window:** [Time range]

## Weekly Trends
[Week-over-week comparison table]

| Week | Total Slot-Hours | Days in Week | Trend |
|------|-----------------|--------------|-------|
| [X] | [X] | [X] | [↑/↓/→] |

## Scheduling Recommendations
- Move non-critical workloads to: [time ranges]
- Peak capacity planning needed for: [time ranges]
```

#### File 4: `analysis_results/04_optimization_opportunities.md`
```markdown
# Optimization Opportunities (30-Day Analysis)

## Slot Contention
- **Jobs with Contention:** [X]
- **Impact:** [Description]
- **Recommendation:** [Action items]

## Job Error Analysis
[Table of common error patterns]

| Error Reason | Error Count | Error % | Capacity-Related |
|--------------|-------------|---------|------------------|
| [reason] | [X] | [X]% | [Yes/No] |

**Capacity-Related Errors:**
- **rateLimitExceeded:** [X] occurrences ([X]%)
- **resourcesExceeded:** [X] occurrences ([X]%)

## Job Impact Analysis
[Table showing impact at different commitment levels]

| Scenario | Commitment Slots | Total Jobs | Jobs Exceeding | % Jobs Exceeding | Slot-Hours Exceeding |
|----------|-----------------|------------|----------------|------------------|---------------------|
| Average | [X] | [X] | [X] | [X]% | [X] |
| P50 | [X] | [X] | [X] | [X]% | [X] |
| P90 | [X] | [X] | [X] | [X]% | [X] |
| P95 | [X] | [X] | [X] | [X]% | [X] |

**Interpretation:**
- Shows how many jobs would exceed different commitment levels
- Helps answer: "If we commit to average slots, how many jobs will be affected?"

## Expensive Queries
[Table of top users by bytes scanned]

| User | Query Count | TB Scanned | Avg GB/Query |
|------|------------|------------|--------------|
| [user] | [X] | [X] | [X] |

**Recommendations:**
- Implement partitioning on: [tables]
- Add clustering for: [columns]
- Review queries scanning >[X]GB

## Slow Queries
[Table of slowest queries]

| Job ID | User | Duration (s) | GB Processed |
|--------|------|--------------|--------------|
| [id] | [user] | [X] | [X] |

## Reservation Simulation
[Table showing utilization at different slot levels]

| Reservation Size | Hours Within | Hours Exceeding | Avg Utilization % |
|-----------------|--------------|-----------------|-------------------|
| 50 | [X] | [X] | [X]% |
| 100 | [X] | [X] | [X]% |
| 500 | [X] | [X] | [X]% |

**Optimal Size:** [X] slots ([X]% utilization)
```

#### File 6: `analysis_results/06_storage_and_cost.md`
```markdown
# Storage & Cost Analysis

## Top Storage Consumers
[Table of largest tables]

| Table | Total Size (GB) | Active (GB) | Long Term (GB) | % Long Term |
|-------|-----------------|-------------|----------------|-------------|
| [table] | [X] | [X] | [X] | [X]% |

**Recommendation:**
- Tables with >90% Long Term storage should be evaluated for archival or deletion.
- Verify if "Active" storage tables are actually being queried.

## Potential Cleanup Candidates
[Table of tables older than 90 days]

| Table | Created | Size (GB) |
|-------|---------|-----------|
| [table] | [Date] | [X] |

## Estimated On-Demand Costs
- **Total Bytes Scanned (30d):** [X] TB
- **Estimated Cost:** $[X] (at $6.25/TB)
- **Top Spender:** [User] ($[X])
```

#### File 5: `analysis_results/05_final_recommendation.md`
```markdown
# Final Recommendation

## Current State Summary
- **Slot Metrics:** p10=[X], p25=[X], p50=[X], p95=[X], max=[X]
- **Variability:** CV=[X] ([Stable/Moderate/Variable])
- **Burstiness:** Ratio=[X] ([Low/Medium/High] burst)
- **Top 3 Projects:** [List with slot-hours]
- **Peak Hours:** [Time ranges]
- **Current Configuration:** [On-Demand / Existing Reservation Details]

## Recommended Strategy
**Choice:** [On-Demand / Baseline Commitment / Autoscaling / Hybrid]

**Reasoning:** [2-3 sentences explaining why based on metrics]

**Configuration:**
- Baseline slots: [X] (based on p[10/25])
- Max autoscale: [X] (if applicable)
- Projects to assign: [List]

## Alternative Analysis

### Why Other Options Were Not Recommended

**Option A: Stay On-Demand (PAYG)**
- **Why Considered:** [Reason]
- **Why Rejected:** [Specific reason based on metrics]

**Option B: Autoscaling Reservation (Standard Edition)**
- **Why Considered:** [Reason]
- **Why Rejected/Recommended:** [Specific reason based on metrics]

**Option C: Baseline Reservations (Enterprise/Enterprise Plus)**
- **Why Considered:** [Reason]
- **Why Rejected:** [Specific reason based on metrics]

**Option D: Hybrid Approach**
- **Why Considered:** [Reason]
- **Why Rejected/Partially Applied:** [Specific reason based on metrics]

## Optimization Actions
1. **[Action 1]:** [Specific recommendation with expected impact]
2. **[Action 2]:** [Specific recommendation with expected impact]
3. **[Action 3]:** [Specific recommendation with expected impact]

## Implementation Steps

### Step 1: [Action]
```bash
[Commands or instructions]
```

### Step 2: [Action]
```bash
[Commands or instructions]
```

### Step 3: Monitoring Setup
```sql
[Monitoring queries to run regularly]
```

## Validation Criteria
- [ ] Slot utilization: 70-85% of committed capacity (if using commitment)
- [ ] Pending jobs: <5% of total jobs
- [ ] Query performance: No degradation in p95 execution time

## Next Steps
1. Review and approve this recommendation
2. Implement changes during [recommended time window]
3. Monitor for [X] days
4. Re-run analysis in [X] days/weeks to validate
```

## SQL Query Reference

**IMPORTANT**: When running queries, always replace `[YOUR_REGION]` with the user provided region (e.g., `region-us`).

### Query 0.1: List Reservations
```sql
-- Check existing reservations and their configuration
-- Source: https://cloud.google.com/bigquery/docs/information-schema-reservations
SELECT
  reservation_name,
  slot_capacity,
  edition,
  ignore_idle_slots,
  autoscale_max_slots,
  creation_time
FROM
  `region-[YOUR_REGION]`.INFORMATION_SCHEMA.RESERVATIONS_BY_PROJECT
ORDER BY
  creation_time DESC;
```

### Query 0.2: Reservation Assignments
```sql
-- Check which projects/folders/orgs are assigned to reservations
-- Source: https://cloud.google.com/bigquery/docs/information-schema-assignments
SELECT
  reservation_name,
  assignment_id,
  assignee_type,
  assignee_id,
  job_type,
  state
FROM
  `region-[YOUR_REGION]`.INFORMATION_SCHEMA.ASSIGNMENTS_BY_PROJECT
ORDER BY
  reservation_name;
```

### Query 0.2a: Historical Commitments
```sql
-- Analyze historical slot commitments over time
-- Source: Adapted from bigquery-utils/dashboards/system_tables/sql/daily_commitments.sql
-- Provides a daily time-series of active monthly/annual slot commitments
WITH
  commitments AS (
    SELECT
      change_timestamp,
      EXTRACT(DATE FROM change_timestamp) AS start_date,
      IFNULL(
        LEAD(DATE_SUB(EXTRACT(DATE FROM change_timestamp), INTERVAL 1 DAY))
          OVER (PARTITION BY state ORDER BY change_timestamp),
        CURRENT_DATE()) AS stop_date,
      SUM(CASE WHEN action IN ('CREATE', 'UPDATE') THEN slot_count ELSE slot_count * -1 END)
        OVER (
          PARTITION BY state
          ORDER BY change_timestamp ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS slot_cumulative,
      ROW_NUMBER()
        OVER (
          PARTITION BY EXTRACT(DATE FROM change_timestamp)
          ORDER BY change_timestamp DESC
        ) AS rn
    FROM
      `region-[YOUR_REGION]`.INFORMATION_SCHEMA.CAPACITY_COMMITMENT_CHANGES_BY_PROJECT
    WHERE
      state = 'ACTIVE' AND commitment_plan != 'FLEX'
  ),
  results AS (SELECT * FROM commitments WHERE rn = 1),
  days AS (
    SELECT day
    FROM (SELECT start_date, stop_date FROM results),
    UNNEST(GENERATE_DATE_ARRAY(start_date, stop_date)) day
  )
SELECT
  TIMESTAMP(day) as date,
  LAST_VALUE(slot_cumulative IGNORE NULLS) OVER(ORDER BY day) as committed_slots
FROM days
LEFT JOIN results ON day = DATE(change_timestamp)
ORDER BY date;
```

### Query 0.3: Current Utilization
```sql
-- Analyze actual reservation utilization over 30 days
-- Source: https://cloud.google.com/bigquery/docs/information-schema-jobs-timeline
WITH reservation_usage AS (
  SELECT
    reservation_id,
    TIMESTAMP_TRUNC(period_start, HOUR) as hour,
    SUM(period_slot_ms) / (1000 * 3600) AS slots_used
  FROM
    `region-[YOUR_REGION]`.INFORMATION_SCHEMA.JOBS_TIMELINE_BY_PROJECT
  WHERE
    period_start BETWEEN TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
      AND CURRENT_TIMESTAMP()
    AND reservation_id IS NOT NULL
  GROUP BY reservation_id, hour
),
reservation_config AS (
  SELECT
    reservation_name,
    slot_capacity,
    autoscale_max_slots
  FROM
    `region-[YOUR_REGION]`.INFORMATION_SCHEMA.RESERVATIONS_BY_PROJECT
)
SELECT
  ru.reservation_id,
  rc.slot_capacity as baseline_slots,
  rc.autoscale_max_slots,
  ROUND(AVG(ru.slots_used), 1) as avg_slots_used,
  ROUND(MAX(ru.slots_used), 1) as max_slots_used,
  ROUND(AVG(ru.slots_used) / rc.slot_capacity * 100, 1) as avg_utilization_pct,
  COUNTIF(ru.slots_used < rc.slot_capacity * 0.5) as hours_underutilized,
  COUNTIF(ru.slots_used > rc.slot_capacity) as hours_exceeded_baseline
FROM
  reservation_usage ru
LEFT JOIN
  reservation_config rc ON ru.reservation_id = rc.reservation_name
GROUP BY
  ru.reservation_id, rc.slot_capacity, rc.autoscale_max_slots;
```

### Query 0.4: Idle Slots
```sql
-- Calculate idle/wasted slot capacity over 30 days
-- Source: https://cloud.google.com/bigquery/docs/information-schema-jobs-timeline
WITH hourly_reservation_usage AS (
  SELECT
    reservation_id,
    TIMESTAMP_TRUNC(period_start, HOUR) as hour,
    SUM(period_slot_ms) / (1000 * 3600) AS slots_used
  FROM
    `region-[YOUR_REGION]`.INFORMATION_SCHEMA.JOBS_TIMELINE_BY_PROJECT
  WHERE
    period_start BETWEEN TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
      AND CURRENT_TIMESTAMP()
    AND reservation_id IS NOT NULL
  GROUP BY reservation_id, hour
),
reservation_config AS (
  SELECT
    reservation_name,
    slot_capacity
  FROM
    `region-[YOUR_REGION]`.INFORMATION_SCHEMA.RESERVATIONS_BY_PROJECT
)
SELECT
  ru.reservation_id,
  rc.slot_capacity,
  ROUND(AVG(rc.slot_capacity - ru.slots_used), 1) as avg_idle_slots,
  ROUND(SUM(rc.slot_capacity - ru.slots_used), 1) as total_idle_slot_hours,
  ROUND(AVG((rc.slot_capacity - ru.slots_used) / rc.slot_capacity * 100), 1) as avg_idle_pct
FROM
  hourly_reservation_usage ru
LEFT JOIN
  reservation_config rc ON ru.reservation_id = rc.reservation_name
GROUP BY
  ru.reservation_id, rc.slot_capacity;
```

### Query 0.5: On-Demand Spillover
```sql
-- Identify queries using on-demand vs. reservation slots over 30 days
-- Source: https://cloud.google.com/bigquery/docs/information-schema-jobs
SELECT
  DATE(creation_time) as date,
  COUNT(*) as total_queries,
  COUNTIF(reservation_id IS NULL) as on_demand_queries,
  COUNTIF(reservation_id IS NOT NULL) as reservation_queries,
  ROUND(COUNTIF(reservation_id IS NULL) / COUNT(*) * 100, 1) as on_demand_pct
FROM
  `region-[YOUR_REGION]`.INFORMATION_SCHEMA.JOBS_BY_PROJECT
WHERE
  creation_time BETWEEN TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
    AND CURRENT_TIMESTAMP()
  AND job_type = 'QUERY'
  AND statement_type != 'SCRIPT'
GROUP BY
  date
ORDER BY
  date DESC;
```

### Query 1.1: System-Wide Percentiles
```sql
-- Calculate slot usage percentiles over 30 days
-- Source: https://cloud.google.com/bigquery/docs/information-schema-jobs-timeline#match_slot_usage_behavior_from_administrative_resource_charts
-- Pattern adapted from Google's official percentile calculation example
WITH hourly_usage AS (
  SELECT
    TIMESTAMP_TRUNC(period_start, HOUR) as hour,
    SUM(period_slot_ms) / 1000 AS slot_seconds
  FROM
    `region-[YOUR_REGION]`.INFORMATION_SCHEMA.JOBS_TIMELINE_BY_PROJECT
  WHERE
    period_start BETWEEN TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
      AND CURRENT_TIMESTAMP()
    AND (statement_type != 'SCRIPT' OR statement_type IS NULL)
  GROUP BY hour
)
SELECT
  ROUND(APPROX_QUANTILES(slot_seconds / 3600, 100)[OFFSET(10)], 1) as p10_slots,
  ROUND(APPROX_QUANTILES(slot_seconds / 3600, 100)[OFFSET(25)], 1) as p25_slots,
  ROUND(APPROX_QUANTILES(slot_seconds / 3600, 100)[OFFSET(50)], 1) as p50_slots,
  ROUND(APPROX_QUANTILES(slot_seconds / 3600, 100)[OFFSET(75)], 1) as p75_slots,
  ROUND(APPROX_QUANTILES(slot_seconds / 3600, 100)[OFFSET(95)], 1) as p95_slots,
  ROUND(MAX(slot_seconds / 3600), 1) as max_slots,
  ROUND(AVG(slot_seconds / 3600), 1) as avg_slots,
  ROUND(STDDEV(slot_seconds / 3600), 1) as stddev_slots
FROM hourly_usage;
```

### Query 1.2: Top Consumers
```sql
-- Top 10 projects by slot consumption
-- Source: https://cloud.google.com/bigquery/docs/information-schema-jobs#most_expensive_queries_by_project
-- Pattern adapted from Google's official example for identifying top consumers
SELECT
  project_id,
  ROUND(SUM(total_slot_ms) / (1000 * 60 * 60), 1) AS total_slot_hours,
  COUNT(*) as job_count
FROM
  `region-[YOUR_REGION]`.INFORMATION_SCHEMA.JOBS_BY_PROJECT
WHERE
  creation_time BETWEEN TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
    AND CURRENT_TIMESTAMP()
  AND job_type = 'QUERY'
  AND statement_type != 'SCRIPT'
GROUP BY
  project_id
ORDER BY
  total_slot_hours DESC
LIMIT 10;
```

### Query 1.3: Granular Usage Patterns
```sql
-- Hourly usage patterns by project, user, and job type
-- Source: Adapted from bigquery-utils/dashboards/system_tables/sql/hourly_utilization.sql
-- Enables hybrid strategy recommendations by identifying distinct workload patterns
SELECT
  TIMESTAMP_TRUNC(period_start, HOUR) AS usage_hour,
  EXTRACT(DAYOFWEEK FROM period_start) as day_of_week,
  EXTRACT(HOUR FROM period_start) as hour_of_day,
  project_id,
  user_email,
  job_type,
  ROUND(SUM(period_slot_ms) / (1000 * 60 * 60), 2) AS hourly_slot_usage
FROM
  `region-[YOUR_REGION]`.INFORMATION_SCHEMA.JOBS_TIMELINE_BY_PROJECT
WHERE
  period_start BETWEEN TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
    AND CURRENT_TIMESTAMP()
  AND (statement_type != 'SCRIPT' OR statement_type IS NULL)
GROUP BY 1, 2, 3, 4, 5, 6
ORDER BY usage_hour DESC, hourly_slot_usage DESC
LIMIT 1000;
```

### Query 4.1: Slot Contention
```sql
-- Find jobs with slot contention over 30 days
-- Source: https://cloud.google.com/bigquery/docs/information-schema-jobs#view_jobs_with_slot_contention_insights
-- Official Google pattern for identifying queries with slot contention issues
SELECT
  job_id,
  user_email,
  TIMESTAMP_DIFF(end_time, start_time, SECOND) as duration_seconds,
  ROUND(total_slot_ms / TIMESTAMP_DIFF(end_time, start_time, MILLISECOND), 1) as avg_slots
FROM
  `region-[YOUR_REGION]`.INFORMATION_SCHEMA.JOBS_BY_PROJECT,
  UNNEST(query_info.performance_insights.stage_performance_standalone_insights) as insights
WHERE
  creation_time BETWEEN TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
    AND CURRENT_TIMESTAMP()
  AND job_type = 'QUERY'
  AND state = 'DONE'
  AND insights.slot_contention = TRUE
ORDER BY
  duration_seconds DESC
LIMIT 10;
```

### Query 4.2: Expensive Queries
```sql
-- Find expensive queries by bytes scanned and estimated cost ($6.25/TB)
-- Note: $6.25 is the standard US pricing. Update this constant if your region has different pricing.
-- Source: https://cloud.google.com/bigquery/docs/information-schema-jobs#bytes_processed_per_user_identity
SELECT
  user_email,
  COUNT(*) as query_count,
  ROUND(SUM(total_bytes_processed) / POW(1024, 4), 2) as total_tb_scanned,
  ROUND(SUM(total_bytes_processed) / POW(1024, 4) * 6.25, 2) as estimated_cost_usd,
  ROUND(AVG(total_bytes_processed) / POW(1024, 3), 2) as avg_gb_per_query
FROM
  `region-[YOUR_REGION]`.INFORMATION_SCHEMA.JOBS_BY_PROJECT
WHERE
  creation_time BETWEEN TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
    AND CURRENT_TIMESTAMP()
  AND job_type = 'QUERY'
  AND statement_type != 'SCRIPT'
GROUP BY
  user_email
HAVING
  total_tb_scanned > 1
ORDER BY
  total_tb_scanned DESC
LIMIT 10;
```

### Query 4.3: Slow Queries
```sql
-- Find queries with longest execution times over 30 days
-- Source: https://cloud.google.com/bigquery/docs/information-schema-jobs
SELECT
  job_id,
  user_email,
  TIMESTAMP_DIFF(end_time, start_time, SECOND) as duration_seconds,
  ROUND(total_bytes_processed / POW(1024, 3), 2) as gb_processed,
  ROUND(total_slot_ms / (1000 * 60 * 60), 2) as slot_hours
FROM
  `region-[YOUR_REGION]`.INFORMATION_SCHEMA.JOBS_BY_PROJECT
WHERE
  creation_time BETWEEN TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
    AND CURRENT_TIMESTAMP()
  AND job_type = 'QUERY'
  AND state = 'DONE'
  AND statement_type != 'SCRIPT'
ORDER BY
  duration_seconds DESC
LIMIT 20;
```

### Query 4.4: Reservation Simulation
```sql
-- Simulate reservation utilization at different slot levels over 30 days
-- Source: https://cloud.google.com/bigquery/docs/information-schema-jobs-timeline
WITH hourly_usage AS (
  SELECT
    TIMESTAMP_TRUNC(period_start, HOUR) as hour,
    SUM(period_slot_ms) / (1000 * 3600) AS slots_used
  FROM
    `region-[YOUR_REGION]`.INFORMATION_SCHEMA.JOBS_TIMELINE_BY_PROJECT
  WHERE
    period_start BETWEEN TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
      AND CURRENT_TIMESTAMP()
    AND (statement_type != 'SCRIPT' OR statement_type IS NULL)
  GROUP BY hour
)
SELECT
  50 as reservation_size,
  COUNTIF(slots_used <= 50) as hours_within_reservation,
  COUNTIF(slots_used > 50) as hours_exceeding_reservation,
  ROUND(AVG(CASE WHEN slots_used <= 50 THEN slots_used ELSE 50 END), 1) as avg_utilization,
  ROUND(AVG(CASE WHEN slots_used <= 50 THEN slots_used ELSE 50 END) / 50 * 100, 1) as avg_utilization_pct
FROM hourly_usage
UNION ALL
SELECT
  100 as reservation_size,
  COUNTIF(slots_used <= 100) as hours_within_reservation,
  COUNTIF(slots_used > 100) as hours_exceeding_reservation,
  ROUND(AVG(CASE WHEN slots_used <= 100 THEN slots_used ELSE 100 END), 1) as avg_utilization,
  ROUND(AVG(CASE WHEN slots_used <= 100 THEN slots_used ELSE 100 END) / 100 * 100, 1) as avg_utilization_pct
FROM hourly_usage
UNION ALL
SELECT
  500 as reservation_size,
  COUNTIF(slots_used <= 500) as hours_within_reservation,
  COUNTIF(slots_used > 500) as hours_exceeding_reservation,
  ROUND(AVG(CASE WHEN slots_used <= 500 THEN slots_used ELSE 500 END), 1) as avg_utilization,
  ROUND(AVG(CASE WHEN slots_used <= 500 THEN slots_used ELSE 500 END) / 500 * 100, 1) as avg_utilization_pct
FROM hourly_usage
ORDER BY reservation_size;
```

### Query 4.5: Usage Trends
```sql
-- Week-over-week slot usage comparison over 30 days
-- Source: https://cloud.google.com/bigquery/docs/information-schema-jobs-timeline
SELECT
  EXTRACT(WEEK FROM DATE(period_start)) as week_number,
  ROUND(SUM(period_slot_ms) / (1000 * 60 * 60), 1) AS total_slot_hours,
  COUNT(DISTINCT DATE(period_start)) as days_in_week
FROM
  `region-[YOUR_REGION]`.INFORMATION_SCHEMA.JOBS_TIMELINE_BY_PROJECT
WHERE
  period_start BETWEEN TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
    AND CURRENT_TIMESTAMP()
  AND (statement_type != 'SCRIPT' OR statement_type IS NULL)
GROUP BY
  week_number
ORDER BY
  week_number;
```

### Query 4.8: Error Analysis
```sql
-- Analyze job error patterns over 30 days
-- Source: Adapted from bigquery-utils/dashboards/system_tables/sql/job_error.sql
-- Identifies the most common reasons for query failures
SELECT
  error_result.reason,
  error_result.message,
  COUNT(*) AS error_count,
  ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 1) as error_pct
FROM
  `region-[YOUR_REGION]`.INFORMATION_SCHEMA.JOBS_BY_PROJECT
WHERE
  creation_time BETWEEN TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
    AND CURRENT_TIMESTAMP()
  AND error_result.reason IS NOT NULL
  AND job_type = 'QUERY'
  AND statement_type != 'SCRIPT'
GROUP BY 1, 2
ORDER BY error_count DESC
LIMIT 10;
```

### Query 4.9: Job Impact Analysis
```sql
-- Analyze job distribution and impact at different slot commitment levels
-- Answers: "If we commit to X slots, how many jobs will exceed that and need on-demand/autoscaling?"
WITH job_slot_usage AS (
  SELECT
    job_id,
    user_email,
    project_id,
    TIMESTAMP_DIFF(end_time, start_time, SECOND) as duration_seconds,
    ROUND(total_slot_ms / TIMESTAMP_DIFF(end_time, start_time, MILLISECOND), 1) as avg_slots_per_job,
    ROUND(total_slot_ms / (1000 * 60 * 60), 2) as slot_hours
  FROM
    `region-[YOUR_REGION]`.INFORMATION_SCHEMA.JOBS_BY_PROJECT
  WHERE
    creation_time BETWEEN TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
      AND CURRENT_TIMESTAMP()
    AND job_type = 'QUERY'
    AND state = 'DONE'
    AND statement_type != 'SCRIPT'
    AND end_time > start_time
),
percentiles AS (
  SELECT
    ROUND(AVG(avg_slots_per_job), 1) as avg_commitment_level,
    ROUND(APPROX_QUANTILES(avg_slots_per_job, 100)[OFFSET(50)], 1) as p50_commitment_level,
    ROUND(APPROX_QUANTILES(avg_slots_per_job, 100)[OFFSET(75)], 1) as p75_commitment_level,
    ROUND(APPROX_QUANTILES(avg_slots_per_job, 100)[OFFSET(90)], 1) as p90_commitment_level,
    ROUND(APPROX_QUANTILES(avg_slots_per_job, 100)[OFFSET(95)], 1) as p95_commitment_level
  FROM job_slot_usage
)
SELECT
  'Average Commitment' as scenario,
  p.avg_commitment_level as commitment_slots,
  COUNT(*) as total_jobs,
  COUNTIF(j.avg_slots_per_job <= p.avg_commitment_level) as jobs_within_commitment,
  COUNTIF(j.avg_slots_per_job > p.avg_commitment_level) as jobs_exceeding_commitment,
  ROUND(COUNTIF(j.avg_slots_per_job > p.avg_commitment_level) * 100.0 / COUNT(*), 1) as pct_jobs_exceeding,
  ROUND(SUM(CASE WHEN j.avg_slots_per_job > p.avg_commitment_level THEN j.slot_hours ELSE 0 END), 1) as slot_hours_exceeding
FROM job_slot_usage j, percentiles p
GROUP BY p.avg_commitment_level

UNION ALL

SELECT
  'P50 Commitment' as scenario,
  p.p50_commitment_level as commitment_slots,
  COUNT(*) as total_jobs,
  COUNTIF(j.avg_slots_per_job <= p.p50_commitment_level) as jobs_within_commitment,
  COUNTIF(j.avg_slots_per_job > p.p50_commitment_level) as jobs_exceeding_commitment,
  ROUND(COUNTIF(j.avg_slots_per_job > p.p50_commitment_level) * 100.0 / COUNT(*), 1) as pct_jobs_exceeding,
  ROUND(SUM(CASE WHEN j.avg_slots_per_job > p.p50_commitment_level THEN j.slot_hours ELSE 0 END), 1) as slot_hours_exceeding
FROM job_slot_usage j, percentiles p
GROUP BY p.p50_commitment_level

UNION ALL

SELECT
  'P90 Commitment' as scenario,
  p.p90_commitment_level as commitment_slots,
  COUNT(*) as total_jobs,
  COUNTIF(j.avg_slots_per_job <= p.p90_commitment_level) as jobs_within_commitment,
  COUNTIF(j.avg_slots_per_job > p.p90_commitment_level) as jobs_exceeding_commitment,
  ROUND(COUNTIF(j.avg_slots_per_job > p.p90_commitment_level) * 100.0 / COUNT(*), 1) as pct_jobs_exceeding,
  ROUND(SUM(CASE WHEN j.avg_slots_per_job > p.p90_commitment_level THEN j.slot_hours ELSE 0 END), 1) as slot_hours_exceeding
FROM job_slot_usage j, percentiles p
GROUP BY p.p90_commitment_level

UNION ALL

SELECT
  'P95 Commitment' as scenario,
  p.p95_commitment_level as commitment_slots,
  COUNT(*) as total_jobs,
  COUNTIF(j.avg_slots_per_job <= p.p95_commitment_level) as jobs_within_commitment,
  COUNTIF(j.avg_slots_per_job > p.p95_commitment_level) as jobs_exceeding_commitment,
  ROUND(COUNTIF(j.avg_slots_per_job > p.p95_commitment_level) * 100.0 / COUNT(*), 1) as pct_jobs_exceeding,
  ROUND(SUM(CASE WHEN j.avg_slots_per_job > p.p95_commitment_level THEN j.slot_hours ELSE 0 END), 1) as slot_hours_exceeding
FROM job_slot_usage j, percentiles p
GROUP BY p.p95_commitment_level

ORDER BY commitment_slots;
```

### Query 6.1: Storage Analysis
```sql
-- Analyze table storage by Active vs Long Term bytes
-- Source: https://cloud.google.com/bigquery/docs/information-schema-table-storage
SELECT
  table_schema,
  table_name,
  ROUND((active_logical_bytes + long_term_logical_bytes + active_physical_bytes + long_term_physical_bytes) / POW(1024, 3), 2) as total_storage_gb,
  ROUND((active_logical_bytes + active_physical_bytes) / POW(1024, 3), 2) as active_storage_gb,
  ROUND((long_term_logical_bytes + long_term_physical_bytes) / POW(1024, 3), 2) as long_term_storage_gb,
  ROUND((long_term_logical_bytes + long_term_physical_bytes) / NULLIF((active_logical_bytes + long_term_logical_bytes + active_physical_bytes + long_term_physical_bytes), 0) * 100, 1) as long_term_pct
FROM
  `region-[YOUR_REGION]`.INFORMATION_SCHEMA.TABLE_STORAGE_BY_PROJECT
WHERE
  total_rows > 0
ORDER BY
  total_storage_gb DESC
LIMIT 20;
```

### Query 6.2: Old Tables (Cleanup Candidates)
```sql
-- Identify tables created > 90 days ago with storage size
-- Source: https://cloud.google.com/bigquery/docs/information-schema-tables
SELECT
  t.table_schema,
  t.table_name,
  DATE(t.creation_time) as created_date,
  ROUND(SAFE_DIVIDE(ts.total_logical_bytes, POW(1024, 3)), 2) as size_gb
FROM
  `region-[YOUR_REGION]`.INFORMATION_SCHEMA.TABLES t
JOIN
  `region-[YOUR_REGION]`.INFORMATION_SCHEMA.TABLE_STORAGE_BY_PROJECT ts
  ON t.table_schema = ts.table_schema AND t.table_name = ts.table_name
WHERE
  t.creation_time < TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 90 DAY)
  AND t.table_type = 'BASE TABLE'
ORDER BY
  size_gb DESC
LIMIT 20;
```
