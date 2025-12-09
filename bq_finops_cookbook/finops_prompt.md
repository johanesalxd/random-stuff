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

### 0.2a Analyze Historical Slot Commitments

Understand how your committed capacity has evolved over time:

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

**MCP Tool:** Use `execute_sql` from `bigquery-data-analytics` server

**Interpretation:**
- Shows how committed capacity has changed over time
- Helps identify if current under/over-utilization is a recent issue or long-term pattern
- Useful for understanding capacity planning decisions and their outcomes

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

### 1.3 Analyze Granular Usage Patterns

Understand usage patterns by project, user, and job type to enable workload segmentation:

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

**MCP Tool:** Use `execute_sql` from `bigquery-data-analytics` server

**Interpretation:**
- Identifies which projects have stable vs. variable usage patterns
- Shows which users or teams drive peak usage
- Enables Hybrid Strategy: assign stable projects to reservations, keep variable projects on-demand
- Helps answer: "Should different projects get different workload management strategies?"

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

### Validation Checkpoint

Before proceeding to strategy recommendation, validate your analysis:

1. **Confidence Check:** Rate your confidence (1-10) in the calculated metrics
2. **Assumption Check:** List any assumptions made about the workload patterns
3. **Data Quality:** Confirm the data covers a representative period (no holidays, migrations, etc.)

## Step 3: Decide on Workload Management Strategy

### Pre-Decision Validation

Before recommending a strategy, validate your understanding:

1. **List All Assumptions:**
   - What assumptions have you made about workload patterns?
   - Are there any seasonal factors not captured in the 30-day window?
   - Have you accounted for planned growth or changes?

2. **Confidence Rating:**
   - Rate your confidence (1-10) in the strategy recommendation
   - Identify any uncertainties that could affect the recommendation
   - Note any additional data that would improve confidence

3. **Stakeholder Alignment:**
   - Confirm the recommendation aligns with business priorities
   - Verify budget constraints are considered
   - Ensure performance requirements are met

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

### 4.8 Analyze Job Error Patterns

Identify common job errors that may indicate capacity or configuration issues:

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

**MCP Tool:** Use `execute_sql` from `bigquery-data-analytics` server

**Interpretation:**
- **`rateLimitExceeded`:** Indicates insufficient capacity, consider increasing reservation size
- **`resourcesExceeded`:** Queries need more slots, may need larger reservation or autoscaling
- **`accessDenied`:** Permission issues, not capacity-related
- **`invalidQuery`:** Query syntax errors, not capacity-related
- **`quotaExceeded`:** Project-level quota limits, may need quota increase

**Actions:**
- High rate of capacity-related errors (>5% of queries): Strong signal to increase committed capacity
- Sporadic capacity errors: Current strategy may be adequate, errors are acceptable
- Non-capacity errors: Address through query fixes or permission updates

### 4.9 Analyze Job Impact at Different Commitment Levels

Understand how many jobs would be affected if using average slots as a baseline commitment:

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

**MCP Tool:** Use `execute_sql` from `bigquery-data-analytics` server

**Interpretation:**
- **jobs_exceeding_commitment:** Number of jobs that would need on-demand or autoscaling capacity
- **pct_jobs_exceeding:** Percentage of jobs affected by the commitment level
- **slot_hours_exceeding:** Total slot-hours that would spill over to on-demand/autoscaling

**Use Case:**
- Answers the question: "If we commit to average slots, how many jobs will be affected?"
- Helps quantify the impact of different commitment levels on workload
- Supports decision-making for baseline vs. autoscaling strategies

**Example Interpretation:**
- If "Average Commitment" shows 80% of jobs exceeding → baseline would be underutilized, autoscaling is better
- If "P90 Commitment" shows only 10% of jobs exceeding → baseline might be appropriate
- High slot_hours_exceeding indicates significant on-demand costs even with commitment

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

## Job Error Analysis
[Table of common error patterns]

| Error Reason | Error Count | Error % | Capacity-Related |
|--------------|-------------|---------|------------------|
| [reason] | [X] | [X]% | [Yes/No] |

**Capacity-Related Errors:**
- **rateLimitExceeded:** [X] occurrences ([X]%)
- **resourcesExceeded:** [X] occurrences ([X]%)

**Recommendations:**
- If capacity errors >5%: Increase reservation size or switch to committed capacity
- If capacity errors <5%: Current strategy adequate
- Non-capacity errors: Address through query fixes or permission updates

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
- High % jobs exceeding indicates baseline would be underutilized

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
