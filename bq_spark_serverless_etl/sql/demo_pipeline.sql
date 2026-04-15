-- demo_pipeline.sql
--
-- Two-step pipeline demonstration:
--
--   Step 1: Ingest data from Cloud SQL Postgres into BigQuery
--           using the Spark Stored Procedure (run_pipeline).
--           Each CALL spins up a Dataproc Serverless Spark job,
--           reads from the source database, and writes to raw_thelook.
--
--   Step 2: Build downstream analytics tables using standard BigQuery SQL.
--           No Spark required -- pure SQL on top of the ingested data.
--
-- Run via:
--   bq query \
--     --project_id=MY_PROJECT \
--     --location=MY_REGION \
--     --nouse_legacy_sql \
--     < sql/demo_pipeline.sql
--
-- Or: make run-demo-pipeline
--
-- Note: The three CALL statements in Step 1 run sequentially within this
-- script. For parallel ingestion, submit them as separate bq query jobs.

-- ============================================================================
-- STEP 1: Ingest from Cloud SQL Postgres -> BigQuery (via Spark)
-- ============================================================================

-- Full load: replace orders table on every run
CALL `MY_PROJECT.MY_DATASET.run_pipeline`(
    'demo_cluster',  -- source_name (maps to configs/demo_cluster.yaml in GCS)
    'thelook',       -- db_name    (database in data_config)
    'orders',        -- tbl_name   (table within the database)
    'MY_GCS_BUCKET',
    'MY_PROJECT',
    GENERATE_UUID(),
    '',              -- source_type: '' = flat path
    ''               -- source_group: '' = flat path
);

-- Upsert: merge users on primary key (id), safe to run multiple times
CALL `MY_PROJECT.MY_DATASET.run_pipeline`(
    'demo_cluster',
    'thelook',
    'users',
    'MY_GCS_BUCKET',
    'MY_PROJECT',
    GENERATE_UUID(),
    '',
    ''
);

-- Incremental: append only new order_items since last watermark
CALL `MY_PROJECT.MY_DATASET.run_pipeline`(
    'demo_cluster',
    'thelook',
    'order_items',
    'MY_GCS_BUCKET',
    'MY_PROJECT',
    GENERATE_UUID(),
    '',
    ''
);

-- ============================================================================
-- STEP 2: Downstream transforms -- plain BigQuery SQL
-- ============================================================================

-- daily_revenue: aggregate revenue by order date and country.
-- Joins across all three ingested tables.
CREATE OR REPLACE TABLE `MY_PROJECT.analytics.daily_revenue`
PARTITION BY order_date
CLUSTER BY country
AS
WITH
order_revenue AS (
  SELECT
    oi.order_id,
    oi.user_id,
    DATE(oi.created_at) AS order_date,
    SUM(oi.sale_price)  AS revenue,
    COUNT(*)            AS item_count
  FROM `MY_PROJECT.raw_thelook.order_items` AS oi
  GROUP BY 1, 2, 3
)

SELECT
  r.order_date,
  u.country,
  u.gender,
  o.status                        AS order_status,
  COUNT(DISTINCT r.order_id)      AS total_orders,
  SUM(r.item_count)               AS total_items,
  ROUND(SUM(r.revenue), 2)        AS total_revenue,
  ROUND(AVG(r.revenue), 2)        AS avg_order_value
FROM order_revenue AS r
INNER JOIN `MY_PROJECT.raw_thelook.orders` AS o USING (order_id)
INNER JOIN `MY_PROJECT.raw_thelook.users`  AS u ON r.user_id = u.id
GROUP BY
  r.order_date,
  u.country,
  u.gender,
  o.status;
