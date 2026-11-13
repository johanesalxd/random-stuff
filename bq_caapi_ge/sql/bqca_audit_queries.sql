-- ============================================================================
-- BigQuery Conversational Analytics (BQCA) & ADK Audit Queries
-- Target: BigQuery Studio / bq CLI Interactive & Attribution Queries
--
-- NOTES & PERMISSIONS:
-- 1. Region qualifier: Default is `region-us`. If your dataset resides in another
--    region (e.g. `region-asia-southeast1`, `region-eu`), update the dataset qualifier
--    `region-<location>.INFORMATION_SCHEMA.JOBS_BY_PROJECT` accordingly.
-- 2. Privileges: Requires `bigquery.jobs.listAll` (e.g., BigQuery Admin or Resource Viewer)
--    to query project-wide or org-wide job telemetry. Standard users can only view their own jobs.
-- 3. Telemetry Retention: INFORMATION_SCHEMA.JOBS retains metadata for 180 days.
-- 4. Label Conventions:
--    - `ca-bq-job = 'true'`: Observed BigQuery service label attached by Conversational Analytics.
--    - `data-agent-id = '<agent_id>'`: Observed BQCA service label identifying the target agent.
--    - `bqca-role = '<role_slug>'`: Attached by Layer 3 / ADK in impersonated service account mode.
--    - `bqca-user-hash = '<sha256>'`: Truncated hash of caller identity attached for auditing.
-- ============================================================================

-- ============================================================================
-- Q1. Label Discovery on Recent Query Jobs (Last 35 Days)
-- Purpose: Discover active BQCA and agent label keys while excluding script wrappers.
-- ============================================================================
SELECT
  job_id,
  creation_time,
  user_email,
  job_type,
  statement_type,
  total_bytes_billed,
  ARRAY(SELECT AS STRUCT key, value FROM UNNEST(labels)) AS labels,
  ARRAY(SELECT CONCAT(rt.dataset_id, '.', rt.table_id) FROM UNNEST(referenced_tables) rt) AS referenced_tables
FROM `region-us.INFORMATION_SCHEMA.JOBS_BY_PROJECT`
WHERE creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 35 DAY)
  AND statement_type IS DISTINCT FROM 'SCRIPT'
  AND EXISTS (
    SELECT 1 FROM UNNEST(labels) l
    WHERE l.key LIKE 'ca%'
       OR l.key LIKE '%agent%'
       OR l.key LIKE '%conversational%'
       OR l.key LIKE '%gemini%'
       OR l.key LIKE 'bqca%'
  )
ORDER BY creation_time DESC
LIMIT 100;

-- ============================================================================
-- Q2. All BQCA & Layer-3 Role-Scoped Jobs (Last 35 Days)
-- Purpose: Filter directly on observed BQCA service label (`ca-bq-job = 'true'`)
--          or Layer-3 impersonation label (`bqca-role IS NOT NULL`).
-- ============================================================================
SELECT
  creation_time,
  job_id,
  user_email,
  (SELECT value FROM UNNEST(labels) WHERE key = 'data-agent-id') AS data_agent_id,
  (SELECT value FROM UNNEST(labels) WHERE key = 'bqca-role') AS bqca_role,
  (SELECT value FROM UNNEST(labels) WHERE key = 'bqca-user-hash') AS bqca_user_hash,
  statement_type,
  total_bytes_billed,
  (
    SELECT STRING_AGG(CONCAT(rt.dataset_id, '.', rt.table_id), ', ')
    FROM UNNEST(referenced_tables) rt
  ) AS referenced_tables,
  query
FROM `region-us.INFORMATION_SCHEMA.JOBS_BY_PROJECT`
WHERE creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 35 DAY)
  AND statement_type IS DISTINCT FROM 'SCRIPT'
  AND (
    EXISTS (SELECT 1 FROM UNNEST(labels) l WHERE l.key = 'ca-bq-job' AND l.value = 'true')
    OR EXISTS (SELECT 1 FROM UNNEST(labels) l WHERE l.key = 'bqca-role')
  )
ORDER BY creation_time DESC;

-- ============================================================================
-- Q3. Daily Per-Agent & Per-Role On-Demand Usage & Cost Rollup
-- Purpose: Aggregates daily job counts, bytes billed, and estimated On-Demand spend.
-- Note: Evaluated at default list rate $6.25 per TiB (POW(1024, 4) bytes).
-- ============================================================================
SELECT
  COALESCE(
    (SELECT value FROM UNNEST(labels) WHERE key = 'data-agent-id'),
    '(adk-direct)'
  ) AS data_agent_id,
  COALESCE(
    (SELECT value FROM UNNEST(labels) WHERE key = 'bqca-role'),
    '(native-ca)'
  ) AS bqca_role,
  EXTRACT(DATE FROM creation_time) AS usage_date,
  user_email,
  COUNT(1) AS total_jobs,
  SUM(total_bytes_billed) AS total_bytes_billed,
  ROUND(SUM(total_bytes_billed) / POW(1024, 4), 4) AS total_tib_billed,
  ROUND(SAFE_DIVIDE(SUM(total_bytes_billed), POW(1024, 4)) * 6.25, 4) AS est_cost_usd_ondemand
FROM `region-us.INFORMATION_SCHEMA.JOBS_BY_PROJECT`
WHERE creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 35 DAY)
  AND statement_type IS DISTINCT FROM 'SCRIPT'
  AND (
    EXISTS (SELECT 1 FROM UNNEST(labels) l WHERE l.key = 'ca-bq-job' AND l.value = 'true')
    OR EXISTS (SELECT 1 FROM UNNEST(labels) l WHERE l.key = 'bqca-role')
  )
GROUP BY data_agent_id, bqca_role, usage_date, user_email
ORDER BY usage_date DESC, total_jobs DESC;

-- ============================================================================
-- Q4. Single-Job Forensic Lookup
-- Purpose: Correlates a specific query job ID captured from a live agent chat
--          or application audit trail with executed SQL, labels, and timestamps.
-- Usage: Supply query parameter `@job_id` (e.g. bq query --parameter=job_id::bqux_job_xxx)
-- ============================================================================
SELECT
  job_id,
  creation_time,
  start_time,
  end_time,
  user_email,
  statement_type,
  total_bytes_billed,
  total_slot_ms,
  query,
  ARRAY(SELECT AS STRUCT key, value FROM UNNEST(labels)) AS labels,
  ARRAY(SELECT CONCAT(rt.dataset_id, '.', rt.table_id) FROM UNNEST(referenced_tables) rt) AS referenced_tables
FROM `region-us.INFORMATION_SCHEMA.JOBS_BY_PROJECT`
WHERE job_id = @job_id;

-- ============================================================================
-- Q5a. Project-Level Slot Share by Agent & Role (Last 7 Days)
-- Purpose: Slices slot-millisecond compute consumption across JOBS_TIMELINE_BY_PROJECT
--          by agent ID, role slug, and pseudonymous user hash, computing proportional
--          share per reservation pool (or on-demand) at project level without org roles.
-- ============================================================================
WITH timeline_slots AS (
  SELECT
    DATE(t.period_start) AS period_date,
    COALESCE(t.reservation_id, 'on-demand') AS reservation_pool,
    -- Extract attribution labels joined from JOBS_BY_PROJECT
    COALESCE((SELECT value FROM UNNEST(j.labels) WHERE key = 'data-agent-id'), 'unknown-agent') AS data_agent_id,
    COALESCE((SELECT value FROM UNNEST(j.labels) WHERE key = 'bqca-role'), 'unspecified-role') AS bqca_role,
    COALESCE((SELECT value FROM UNNEST(j.labels) WHERE key = 'bqca-user-hash'), 'anon') AS bqca_user_hash,
    COALESCE((SELECT value FROM UNNEST(j.labels) WHERE key = 'ca-bq-job'), 'false') AS is_ca_job,
    t.user_email,
    t.period_slot_ms
  FROM `region-us.INFORMATION_SCHEMA.JOBS_TIMELINE_BY_PROJECT` AS t
  LEFT JOIN `region-us.INFORMATION_SCHEMA.JOBS_BY_PROJECT` AS j
    ON j.project_id = t.project_id
    AND j.job_id = t.job_id
    AND j.creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 8 DAY)
  WHERE t.period_start >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
    AND t.job_type = 'QUERY'
    AND t.statement_type IS DISTINCT FROM 'SCRIPT'
    AND t.period_slot_ms > 0
),
pool_daily_totals AS (
  SELECT
    period_date,
    reservation_pool,
    SUM(period_slot_ms) AS total_pool_slot_ms
  FROM timeline_slots
  GROUP BY 1, 2
),
agent_role_daily_agg AS (
  SELECT
    period_date,
    reservation_pool,
    data_agent_id,
    bqca_role,
    bqca_user_hash,
    is_ca_job,
    user_email,
    SUM(period_slot_ms) AS agent_slot_ms,
    ROUND(SUM(period_slot_ms) / 1000 / 3600, 4) AS slot_hours
  FROM timeline_slots
  GROUP BY 1, 2, 3, 4, 5, 6, 7
)
SELECT
  a.period_date,
  a.reservation_pool,
  a.data_agent_id,
  a.bqca_role,
  a.bqca_user_hash,
  a.is_ca_job,
  a.user_email,
  a.agent_slot_ms,
  a.slot_hours,
  ROUND(SAFE_DIVIDE(a.agent_slot_ms, p.total_pool_slot_ms) * 100, 2) AS pool_slot_share_pct
FROM agent_role_daily_agg AS a
JOIN pool_daily_totals AS p
  ON a.period_date = p.period_date
  AND a.reservation_pool = p.reservation_pool
ORDER BY
  a.period_date DESC,
  a.agent_slot_ms DESC
LIMIT 100;

-- ============================================================================
-- Q5b. Organization-Level Reservation Cost Attribution with Cloud Billing Export
-- Purpose: Allocates daily BigQuery Reservation API net spend proportionally
--          across JOBS_TIMELINE_BY_ORGANIZATION slot-ms (where reservation_id IS NOT NULL
--          and statement_type IS DISTINCT FROM 'SCRIPT').
--
-- REQUIREMENTS & CAVEATS:
-- 1. Org Permissions: Requires `roles/bigquery.admin` or `roles/bigquery.resourceViewer`
--    at Google Cloud Organization level to access JOBS_TIMELINE_BY_ORGANIZATION.
--    Fallback: If org permissions are unavailable, use Q5a at project level.
-- 2. Cloud Billing Export: Replace `my-billing-project.billing_export.gcp_billing_export_resource_v1_XXXXXX`
--    with your designated Cloud Billing export table and dataset.
-- 3. 1-Second Slices & Denominator Isolation: JOBS_TIMELINE_BY_ORGANIZATION slices slot-ms
--    into 1-second periods by actual execution date. Both the job-level CTE and org-level
--    denominator strictly filter `reservation_id IS NOT NULL` to prevent on-demand query
--    slots from diluting reservation cost attribution.
-- 4. Scope & Idle-Slot Caveats: (a) Idle baseline/autoscaled reservation capacity is
--    apportioned across active slot consumers in proportion to used slot-ms; (b) ensure
--    the Cloud Billing export covers the exact same organization/projects as
--    JOBS_TIMELINE_BY_ORGANIZATION; and (c) if mixing Standard/Enterprise/Enterprise Plus
--    reservations under one billing export, join by specific reservation SKU/tier rather
--    than pooling daily reservation spend across editions.
-- ============================================================================
/*
WITH org_job_usage AS (
  SELECT
    t.project_id,
    t.reservation_id,
    t.user_email,
    -- Extract governance and attribution labels attached to the job
    (SELECT value FROM UNNEST(j.labels) WHERE key = 'data-agent-id') AS data_agent_id,
    (SELECT value FROM UNNEST(j.labels) WHERE key = 'bqca-role') AS bqca_role,
    (SELECT value FROM UNNEST(j.labels) WHERE key = 'cost_center') AS cost_center,
    (SELECT value FROM UNNEST(j.labels) WHERE key = 'environment') AS environment,
    DATE(t.period_start) AS usage_date,
    SUM(t.period_slot_ms) AS job_slot_ms
  FROM `region-us.INFORMATION_SCHEMA.JOBS_TIMELINE_BY_ORGANIZATION` t
  LEFT JOIN `region-us.INFORMATION_SCHEMA.JOBS_BY_ORGANIZATION` j
    ON j.project_id = t.project_id
    AND j.job_id = t.job_id
    AND j.creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 90 DAY)
  WHERE t.period_start >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
    AND t.statement_type IS DISTINCT FROM 'SCRIPT'
    AND t.period_slot_ms > 0
    AND t.reservation_id IS NOT NULL
  GROUP BY 1, 2, 3, 4, 5, 6, 7, 8
),
reservation_daily_totals AS (
  SELECT
    reservation_id,
    usage_date,
    SUM(job_slot_ms) AS total_reservation_slot_ms
  FROM org_job_usage
  WHERE reservation_id IS NOT NULL
  GROUP BY 1, 2
),
total_daily_compute AS (
  SELECT
    usage_date,
    SUM(job_slot_ms) AS total_org_slot_ms
  FROM org_job_usage
  WHERE reservation_id IS NOT NULL
  GROUP BY 1
),
daily_reservation_spend AS (
  SELECT
    DATE(usage_start_time) AS billing_date,
    SUM(cost) + SUM(IFNULL((SELECT SUM(c.amount) FROM UNNEST(credits) c), 0)) AS net_reservation_spend
  FROM `my-billing-project.billing_export.gcp_billing_export_resource_v1_XXXXXX`
  WHERE _PARTITIONDATE >= DATE_SUB(CURRENT_DATE(), INTERVAL 31 DAY)
    AND service.description = 'BigQuery Reservation API'
    AND (
      sku.description LIKE '%Enterprise%'
      OR sku.description LIKE '%Capacity%'
      OR sku.description LIKE '%Reservation%'
      OR sku.description LIKE '%Edition%'
    )
  GROUP BY 1
)
SELECT
  u.usage_date,
  u.project_id AS consuming_project_id,
  u.reservation_id,
  u.data_agent_id,
  u.bqca_role,
  u.cost_center,
  u.environment,
  u.user_email,
  u.job_slot_ms,
  ROUND(u.job_slot_ms / 1000 / 3600, 2) AS slot_hours_consumed,
  ROUND(SAFE_DIVIDE(u.job_slot_ms, r.total_reservation_slot_ms) * 100, 2) AS within_reservation_share_pct,
  ROUND(SAFE_DIVIDE(u.job_slot_ms, t.total_org_slot_ms) * 100, 2) AS total_org_share_pct,
  ROUND(SAFE_DIVIDE(u.job_slot_ms, t.total_org_slot_ms) * b.net_reservation_spend, 2) AS attributed_net_spend
FROM org_job_usage u
JOIN reservation_daily_totals r
  ON u.reservation_id = r.reservation_id
  AND u.usage_date = r.usage_date
JOIN total_daily_compute t
  ON u.usage_date = t.usage_date
LEFT JOIN daily_reservation_spend b
  ON u.usage_date = b.billing_date
ORDER BY u.usage_date DESC, attributed_net_spend DESC;
*/
