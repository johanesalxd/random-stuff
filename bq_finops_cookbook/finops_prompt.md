# BigQuery Slot Optimization Guide

You are a BigQuery administrator analyzing slot utilization to optimize workload management. Your goal is to understand current usage patterns and recommend the best workload management strategy.

## Prerequisites

- Access to `INFORMATION_SCHEMA.JOBS_BY_PROJECT` and `INFORMATION_SCHEMA.JOBS_TIMELINE_BY_PROJECT`
- BigQuery Resource Viewer role (`roles/bigquery.resourceViewer`)
- Project ID: `[YOUR_GCP_PROJECT_ID]`
- Region: `[YOUR_REGION]` (e.g., `us`, `eu`, `asia-northeast1`)

## Before You Start: Handling Schema Errors

If you encounter "Unrecognized name" errors when running queries:

1. Replace the SELECT clause with `SELECT *` to see all available fields
2. Identify which fields exist in your BigQuery edition
3. Modify the query to use only the available fields

**Example:**
```sql
-- If this fails with "Unrecognized name: autoscale_max_slots"
SELECT reservation_name, slot_capacity, autoscale_max_slots
FROM `region-us`.INFORMATION_SCHEMA.RESERVATIONS_BY_PROJECT;

-- Use this instead to discover available fields
SELECT *
FROM `region-us`.INFORMATION_SCHEMA.RESERVATIONS_BY_PROJECT
LIMIT 1;

-- Then adjust your query based on what fields actually exist
SELECT reservation_name, slot_capacity
FROM `region-us`.INFORMATION_SCHEMA.RESERVATIONS_BY_PROJECT;
```

**Note:** Field availability varies by BigQuery edition (Standard/Enterprise/Enterprise Plus).

## About the SQL Queries

**Query Validation Status:** All SQL queries in this guide are validated against the latest official Google Cloud BigQuery documentation and represent current best practices.

**Using the Provided Queries:**
- The queries are production-ready and can be used as-is
- Each query includes source documentation URLs for reference
- All queries use correct schema and syntax verified against Google's official examples
- Proper NULL handling and filtering patterns are implemented

**Customizing Queries:**
If you need to modify these queries for specific requirements:

1. **Test in Development First**
   - Always test modifications in a non-production environment
   - Verify results match expected output before using in production

2. **Maintain Core Patterns**
   - Keep the fundamental query structure intact
   - Preserve the UNNEST patterns for nested fields
   - Maintain the `statement_type != 'SCRIPT'` filter to avoid double-counting

3. **Reference Official Documentation**
   - Use the provided source URLs to understand schema details
   - Check Google's documentation for any schema changes
   - Verify field names and data types before modifying

4. **Common Customizations**
   - Adjust time ranges (e.g., change from 30 days to 60 days)
   - Add additional filters for specific projects or users
   - Modify aggregation levels (e.g., daily instead of hourly)
   - Include additional columns from the schema

5. **Avoid Common Pitfalls**
   - Don't remove NULL checks for nested fields (e.g., `performance_insights`)
   - Don't forget to use region qualifiers (`` `region-[YOUR_REGION]` ``)
   - Don't include `SCRIPT` statement types in aggregations
   - Don't assume field availability without checking the schema

**Getting Help:**
- Refer to the References section for official documentation links
- Check the source URL comments in each query for specific examples
- Review Google's INFORMATION_SCHEMA documentation for schema changes

## Step 0: Assess Current Configuration

Before analyzing usage patterns, understand your current workload management setup. This step is critical for organizations that already have reservations configured.

### 0.1 List Existing Reservations

Check if you have any existing reservations and their configuration:

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

**MCP Tool:** Use `execute_sql` from `bigquery-data-analytics` server

### 0.2 Analyze Reservation Assignments

Identify which projects, folders, or organizations are assigned to reservations:

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

**MCP Tool:** Use `execute_sql` from `bigquery-data-analytics` server

### 0.3 Calculate Current Reservation Utilization

Analyze how well your existing reservations are being utilized:

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

**MCP Tool:** Use `execute_sql` from `bigquery-data-analytics` server

### 0.4 Identify Idle Slots (Waste)

Calculate how much committed capacity is sitting idle:

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

**MCP Tool:** Use `execute_sql` from `bigquery-data-analytics` server

### 0.5 Check for On-Demand Spillover

Identify queries that exceeded reservation capacity and used on-demand slots:

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

**MCP Tool:** Use `execute_sql` from `bigquery-data-analytics` server

**Interpretation:**
- **No reservations found:** Skip to Step 1 to analyze usage patterns
- **High idle percentage (>30%):** Reservation is over-provisioned
- **Frequent spillover to on-demand:** Reservation is under-provisioned
- **Good utilization (70-85%):** Reservation is well-sized

## Step 1: Analyze Current Slot Usage

### 1.1 Get System-Wide Slot Percentiles

Run this query to understand your overall slot utilization pattern:

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

**MCP Tool:** Use `execute_sql` from `bigquery-data-analytics` server

### 1.2 Identify Top Slot Consumers

Find which projects are using the most slots:

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

**MCP Tool:** Use `execute_sql` from `bigquery-data-analytics` server

### 1.3 Analyze Usage Patterns by Time

Understand when peak usage occurs:

```sql
-- Hourly usage pattern by day of week
-- Source: https://cloud.google.com/bigquery/docs/information-schema-jobs-timeline
-- Custom query to identify peak usage periods for workload scheduling
SELECT
  EXTRACT(DAYOFWEEK FROM period_start) as day_of_week,
  EXTRACT(HOUR FROM period_start) as hour_of_day,
  ROUND(AVG(period_slot_ms) / 1000, 1) as avg_slot_seconds,
  ROUND(MAX(period_slot_ms) / 1000, 1) as max_slot_seconds
FROM
  `region-[YOUR_REGION]`.INFORMATION_SCHEMA.JOBS_TIMELINE_BY_PROJECT
WHERE
  period_start BETWEEN TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
    AND CURRENT_TIMESTAMP()
  AND (statement_type != 'SCRIPT' OR statement_type IS NULL)
GROUP BY
  day_of_week, hour_of_day
ORDER BY
  day_of_week, hour_of_day;
```

**MCP Tool:** Use `execute_sql` from `bigquery-data-analytics` server

## Step 2: Characterize Your Workload

Based on the query results, calculate these key metrics:

**Stability Metric:**
```
Coefficient of Variation = stddev_slots / avg_slots
- Low variability: < 0.5 (stable workload)
- Medium variability: 0.5 - 1.0 (moderate fluctuation)
- High variability: > 1.0 (highly variable)
```

**Burstiness Metric:**
```
Burst Ratio = p95_slots / p50_slots
- Low burst: < 2 (consistent usage)
- Medium burst: 2 - 4 (moderate peaks)
- High burst: > 4 (significant spikes)
```

**MCP Tool:** Use `ask_data_insights` from `bigquery-conversational-analytics` server to interpret patterns

## Step 3: Decide on Workload Management Strategy

Based on your metrics, choose the appropriate strategy:

### Option A: Stay On-Demand (PAYG)
**Recommend when:**
- Average slots < 100
- High variability (CV > 1.0)
- Unpredictable, sporadic usage
- Development/testing environments

**Action:** No changes needed. Continue with on-demand billing.

**Monitoring:** Track monthly slot-hour consumption for budget planning.

---

### Option B: Baseline Commitment (Standard/Enterprise Edition)
**Recommend when:**
- p25 slots ≥ 50 (meets minimum)
- Low to medium variability (CV < 1.0)
- Stable baseline with manageable peaks
- Production workloads with consistent patterns

**Baseline Size:** Use p10 or p25 percentile (whichever is ≥ 50 slots)

**Implementation:**
```bash
# Create reservation
bq mk --reservation \
  --project=[PROJECT_ID] \
  --location=[REGION] \
  --slots=[BASELINE_SLOTS] \
  production_baseline

# Assign top projects to reservation
bq mk --reservation_assignment \
  --project=[PROJECT_ID] \
  --location=[REGION] \
  --reservation=production_baseline \
  --job_type=QUERY \
  --assignee_type=PROJECT \
  --assignee_id=[TOP_PROJECT_ID]
```

**Peak Handling:** Queries exceeding baseline will use on-demand slots automatically.

---

### Option C: Autoscaling Commitment (Enterprise Plus Edition)
**Recommend when:**
- p25 slots ≥ 50 (baseline requirement)
- High burst ratio (p95/p50 > 3)
- Predictable peak patterns
- Need guaranteed capacity during bursts

**Baseline Size:** Use p25 percentile
**Max Autoscale:** Set to p95 percentile

**Implementation:**
```bash
# Create autoscaling reservation
bq mk --reservation \
  --project=[PROJECT_ID] \
  --location=[REGION] \
  --slots=[BASELINE_SLOTS] \
  --max_autoscale_slots=[MAX_SLOTS] \
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

**Benefit:** Automatically scales up during peaks, scales down during quiet periods.

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

## Step 4: Optimization Recommendations

Beyond reservation strategy, identify specific optimization opportunities:

### 4.1 Check for Slot Contention

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

**Action:** If many jobs show slot contention, consider increasing reservation size.

### 4.2 Identify Query Optimization Opportunities

```sql
-- Find expensive queries by bytes scanned over 30 days
-- Source: https://cloud.google.com/bigquery/docs/information-schema-jobs#bytes_processed_per_user_identity
-- Pattern adapted from Google's official example for identifying high-cost users
SELECT
  user_email,
  COUNT(*) as query_count,
  ROUND(SUM(total_bytes_processed) / POW(1024, 4), 2) as total_tb_scanned,
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

**Actions:**
- Implement partitioning on large tables
- Add clustering keys for common filter columns
- Review and optimize queries scanning >100GB

### 4.3 Identify Slow Queries

Find queries with longest execution times that might benefit from optimization:

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

**MCP Tool:** Use `execute_sql` from `bigquery-data-analytics` server

**Actions:**
- Review queries taking >5 minutes
- Check for missing partitioning/clustering
- Optimize JOIN operations
- Consider materialized views for repeated aggregations

### 4.4 Simulate Reservation Utilization

Analyze how a hypothetical reservation would have been utilized:

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

**MCP Tool:** Use `execute_sql` from `bigquery-data-analytics` server

**Interpretation:**
- Target 70-85% average utilization for optimal efficiency
- High spillover hours indicate under-provisioning
- Low utilization percentage indicates over-provisioning

### 4.5 Analyze Usage Trends

Review week-over-week trends to identify growth patterns:

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

**MCP Tool:** Use `execute_sql` from `bigquery-data-analytics` server

**Actions:**
- Identify growth trends (increasing slot-hours week-over-week)
- Plan for capacity expansion if consistent growth observed
- Account for seasonal variations in planning

### 4.6 Verify Data Freshness

Check that INFORMATION_SCHEMA data is current:

```sql
-- Check data freshness
-- Source: https://cloud.google.com/bigquery/docs/information-schema-jobs
SELECT
  MAX(creation_time) as latest_job_timestamp,
  TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), MAX(creation_time), HOUR) as hours_since_last_job,
  COUNT(*) as total_jobs_30_days
FROM
  `region-[YOUR_REGION]`.INFORMATION_SCHEMA.JOBS_BY_PROJECT
WHERE
  creation_time BETWEEN TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
    AND CURRENT_TIMESTAMP();
```

**MCP Tool:** Use `execute_sql` from `bigquery-data-analytics` server

**Interpretation:**
- If `hours_since_last_job` > 24, the project may be inactive
- If `total_jobs_30_days` is very low, consider longer analysis period
- Ensure data is recent before making capacity decisions

### 4.7 Schedule Non-Critical Workloads

Based on the hourly pattern analysis from Step 1.3:
- Identify off-peak hours (typically 2-6 AM in your timezone)
- Move batch jobs and non-critical queries to off-peak
- Use Cloud Scheduler or Airflow for automated scheduling

## Step 5: Monitor and Validate

After implementing your chosen strategy, monitor these metrics:

### Key Monitoring Queries

**Daily Slot Utilization:**
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

**Reservation Utilization (if using commitments):**
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

**Success Criteria:**
- Slot utilization: 70-85% of committed capacity
- Pending jobs: <5% of total jobs
- Query performance: No degradation in p95 execution time

## Output Format

Generate separate markdown files in the `analysis_results/` directory for better organization and readability:

### File Structure

```
bq_finops/analysis_results/
├── 00_current_configuration.md (if reservations exist)
├── 01_slot_metrics.md
├── 02_top_consumers.md
├── 03_usage_patterns.md
├── 04_optimization_opportunities.md
└── 05_final_recommendation.md
```

### 00_current_configuration.md (Optional - only if reservations exist)

```markdown
# Current Configuration Analysis

## Existing Reservations
[Table of reservations with slot_capacity, edition, autoscale settings]

## Reservation Assignments
[Table of assignments showing which projects/folders are assigned]

## Current Utilization
- **Reservation:** [name]
- **Baseline Slots:** [X]
- **Autoscale Max:** [X] (if applicable)
- **Average Utilization:** [X]%
- **Hours Underutilized:** [X]
- **Hours Exceeded Baseline:** [X]

## Idle Capacity Analysis
- **Average Idle Slots:** [X]
- **Total Idle Slot-Hours:** [X]
- **Average Idle Percentage:** [X]%

## On-Demand Spillover
[Daily breakdown of on-demand vs. reservation usage]

## Assessment
[Brief assessment of current configuration efficiency]
```

### 01_slot_metrics.md

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

### 02_top_consumers.md

```markdown
# Top Slot Consumers (30-Day Analysis)

## Project Rankings

| Rank | Project ID | Slot-Hours | Job Count |
|------|-----------|------------|-----------|
| 1 | [project-1] | [X] | [X] |
| 2 | [project-2] | [X] | [X] |
| 3 | [project-3] | [X] | [X] |
| ... | ... | ... | ... |

## Analysis
- **Top Consumer:** [project] accounts for [X]% of total usage
- **Concentration:** Top 3 projects represent [X]% of total usage
- **Recommendation:** [Assignment strategy for top consumers]
```

### 03_usage_patterns.md

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
| [X] | [X] | [X] | [↑/↓/→] |

## Scheduling Recommendations
- Move non-critical workloads to: [time ranges]
- Peak capacity planning needed for: [time ranges]
```

### 04_optimization_opportunities.md

```markdown
# Optimization Opportunities (30-Day Analysis)

## Slot Contention
- **Jobs with Contention:** [X]
- **Impact:** [Description]
- **Recommendation:** [Action items]

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

**Recommendations:**
- Optimize queries taking >[X] minutes
- Consider materialized views for: [use cases]

## Reservation Simulation
[Table showing utilization at different slot levels]

| Reservation Size | Hours Within | Hours Exceeding | Avg Utilization % |
|-----------------|--------------|-----------------|-------------------|
| 50 | [X] | [X] | [X]% |
| 100 | [X] | [X] | [X]% |
| 500 | [X] | [X] | [X]% |

**Optimal Size:** [X] slots ([X]% utilization)
```

### 05_final_recommendation.md

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

### Presentation Format

When presenting the analysis to the user:
1. Generate all applicable markdown files in `analysis_results/`
2. Provide a summary in the chat highlighting key findings
3. Direct the user to review the detailed reports in the `analysis_results/` directory
4. Offer to answer questions or make adjustments based on their feedback

## References

### Official Documentation
- [BigQuery Reservations Introduction](https://cloud.google.com/bigquery/docs/reservations-intro) - Workload management models and concepts
- [INFORMATION_SCHEMA.JOBS View](https://cloud.google.com/bigquery/docs/information-schema-jobs) - Job metadata and query examples
- [INFORMATION_SCHEMA.JOBS_TIMELINE View](https://cloud.google.com/bigquery/docs/information-schema-jobs-timeline) - Time-series slot usage analysis
- [Workload Management Best Practices](https://cloud.google.com/bigquery/docs/best-practices-performance-compute) - Performance optimization guidance
- [BigQuery Editions](https://cloud.google.com/bigquery/docs/editions-intro) - Understanding Standard, Enterprise, and Enterprise Plus editions

### Query Pattern Sources
All SQL queries in this guide are based on official Google Cloud BigQuery documentation:

- **Percentile Calculation (Query 1.1):** [Match slot usage behavior from administrative resource charts](https://cloud.google.com/bigquery/docs/information-schema-jobs-timeline#match_slot_usage_behavior_from_administrative_resource_charts)
- **Top Consumers (Query 1.2):** [Most expensive queries by project](https://cloud.google.com/bigquery/docs/information-schema-jobs#most_expensive_queries_by_project)
- **Slot Contention (Query 4.1):** [View jobs with slot contention insights](https://cloud.google.com/bigquery/docs/information-schema-jobs#view_jobs_with_slot_contention_insights)
- **Bytes Processed (Query 4.2):** [Bytes processed per user identity](https://cloud.google.com/bigquery/docs/information-schema-jobs#bytes_processed_per_user_identity)
- **Average Slot Utilization:** [Calculate average slot utilization](https://cloud.google.com/bigquery/docs/information-schema-jobs#calculate_average_slot_utilization)

### Command Reference
- [bq command-line tool reference](https://cloud.google.com/bigquery/docs/reference/bq-cli-reference) - CLI commands for reservation management
- [Creating and managing reservations](https://cloud.google.com/bigquery/docs/reservations-workload-management) - Detailed reservation configuration guide
