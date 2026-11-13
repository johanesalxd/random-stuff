-- ==============================================================================
-- Zero-Downtime 2-Policy BigQuery Row-Level Security (RLS) Pattern
--
-- Target Schema: `my-project.analytics_curated.*`
-- Security Schema: `my-project.security.rls_role_entitlements`
-- Note: Row access policies cannot be applied to read-only public datasets
-- (such as `bigquery-public-data`). Apply this DDL to customer-managed curated tables.
-- ==============================================================================


-- ==============================================================================
-- Section 0: Mandatory Pre-Flight Principal Inventory & Coverage Audit
-- ==============================================================================
--
-- In BigQuery, creating the VERY FIRST row access policy on a table immediately
-- restricts access for ALL principals not explicitly granted in the policy.
-- Principals with standard `dataViewer` permissions who are omitted from the
-- policy will receive ZERO rows silently (no permission error, but empty results)!
--
-- Discovery Query 0.1: Project-Level Query Runner Inventory
-- Run this discovery query over the last 90-180 days across `INFORMATION_SCHEMA.JOBS_BY_PROJECT`
-- to identify every ETL service account, BI dashboard runner, scheduled query owner,
-- and automated catalog scanner before authoring RLS policies.

SELECT
  user_email,
  COUNT(DISTINCT j.job_id) AS distinct_query_jobs,
  MIN(creation_time) AS first_seen,
  MAX(creation_time) AS last_seen,
  ARRAY_AGG(DISTINCT CONCAT(ref.dataset_id, '.', ref.table_id) IGNORE NULLS LIMIT 10) AS referenced_target_tables
FROM
  `region-us`.INFORMATION_SCHEMA.JOBS_BY_PROJECT AS j,
  UNNEST(referenced_tables) AS ref
WHERE
  creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 90 DAY)
  AND ref.project_id = 'my-project'
  AND ref.dataset_id = 'analytics_curated'
  AND ref.table_id IN ('users', 'orders', 'order_items')
  AND job_type = 'QUERY'
  AND state = 'DONE'
  AND error_result IS NULL
GROUP BY
  user_email
ORDER BY
  distinct_query_jobs DESC;

-- CRITICAL PRE-FLIGHT COVERAGE NOTES:
-- Single-project `JOBS_BY_PROJECT` alone is NOT sufficient for enterprise zero-downtime discovery.
-- Three additional verification checks MUST be executed before applying RLS:
--
-- 1. Cross-Project Billing Discovery (`JOBS_BY_ORGANIZATION`):
--    Queries submitted from separate compute/billing projects that read `my-project.analytics_curated`
--    appear in the caller project's job history, NOT `my-project`'s `JOBS_BY_PROJECT`.
--    Re-run the inventory query above against `region-us.INFORMATION_SCHEMA.JOBS_BY_ORGANIZATION`
--    to catch cross-project dashboard, reporting, and ad-hoc analyst traffic.
--
-- 2. Storage Read API Consumer Discovery (Cloud Audit Logs):
--    Apache Spark (Dataproc/Databricks), Apache Beam (Dataflow), BigQuery DataFrames (BigFrames),
--    and high-throughput BI connectors read table data via the BigQuery Storage Read API
--    (`BigQueryRead.CreateReadSession`), which does NOT generate standard SQL query jobs.
--    Query Cloud Audit Logs (`protoPayload.methodName = "google.cloud.bigquery.storage.v1.BigQueryRead.CreateReadSession"`)
--    for read sessions referencing `analytics_curated`.
--    *WARNING*: BigQuery does NOT support subqueries in row access policies when accessed via
--    the Storage Read API. If Storage Read API consumers read these tables, you MUST use
--    Pattern 4A (denormalized filter column) rather than subquery-based RLS!
--
-- 3. Inactive/Dormant Permissions Audit (IAM Policy Export):
--    Export existing dataset-level and table-level IAM bindings (`bigquery.tables.getData` / `roles/bigquery.dataViewer`)
--    using Cloud Asset Inventory or `gcloud bigquery datasets get-iam-policy`.
--    Principals with valid read grants who did not execute queries during the 90-day lookback window
--    (e.g. annual auditor accounts, quarterly reporting pipelines, disaster-recovery automation)
--    must still be enumerated in Section 3 (Policy 1 Bypass) before activation.


-- ==============================================================================
-- Section 1: IAM Grant Matrix (Enforce Least-Privilege Role Separation)
-- ==============================================================================
--
-- 1. Trusted Caller Gateway SA (e.g. `gateway-runner@my-project.iam.gserviceaccount.com`):
--    - `roles/iam.serviceAccountTokenCreator` or `iam.serviceAccounts.signJwt` on ITSELF:
--      Allows signing short-lived OIDC role assertion tokens (RS256) specifying `bqca_role` and `sub`.
--    - `roles/aiplatform.user` on Vertex AI Agent Engine reasoning engine instance:
--      Allows invoking the Agent Engine query session with the signed role assertion token in session state.
--    - ZERO BigQuery IAM roles: Gateway never accesses BigQuery data directly.
--
-- 2. Agent Engine Host SA (e.g. `agent-engine-host@my-project.iam.gserviceaccount.com`):
--    - `roles/iam.serviceAccountTokenCreator` bound STRICTLY on each individual Role SA resource:
--      Example:
--        gcloud iam service-accounts add-iam-policy-binding role-apac@my-project.iam.gserviceaccount.com \
--          --member="serviceAccount:agent-engine-host@my-project.iam.gserviceaccount.com" \
--          --role="roles/iam.serviceAccountTokenCreator"
--      *CRITICAL*: NEVER grant `roles/iam.serviceAccountTokenCreator` at the project level! Project-wide
--      token creator permissions allow the agent host to impersonate any administrative SA.
--    - `roles/bigquery.metadataViewer` on curated datasets:
--      Allows reading schema metadata, column types, and descriptions for NL2SQL grounding.
--    - `roles/dataplex.catalogViewer` on Knowledge Catalog:
--      Allows catalog schema discovery and semantic tag lookups.
--    - ZERO `roles/bigquery.dataViewer` or `roles/bigquery.admin`:
--      Ensures the host agent cannot execute queries or read table rows under its own identity.
--
-- 3. Each Role Service Account (e.g. `role-apac@my-project.iam.gserviceaccount.com`):
--    - `roles/bigquery.jobUser` on the query compute project (`my-project` or `my-compute-project`):
--      Allows creating BigQuery query jobs.
--    - Table-Level `roles/bigquery.dataViewer` ONLY on the specific RLS-protected tables:
--      Grant `dataViewer` on `my-project.analytics_curated.users`, `orders`, and `order_items`.
--      *CRITICAL WARNING - NEVER GRANT roles/bigquery.filteredDataViewer DIRECTLY*:
--      `roles/bigquery.filteredDataViewer` is a system-managed role automatically granted
--      by `CREATE ROW ACCESS POLICY` (see https://docs.cloud.google.com/bigquery/docs/managing-row-level-security).
--      Do NOT attempt to assign `filteredDataViewer` via `gcloud` or IAM policy bindings.
--      *CRITICAL WARNING - SCOPE DATA VIEWER AT TABLE LEVEL, NOT DATASET LEVEL*:
--      Never grant dataset-level `roles/bigquery.dataViewer` on `analytics_curated` to Role SAs.
--      Any table in the dataset that does NOT yet have a row access policy would be completely
--      unfiltered and accessible in full!
--    - Table-Level `roles/bigquery.dataViewer` on the lookup table:
--      Grant on `my-project.security.rls_role_entitlements` (and `user_country_map` if using Pattern 4B).
--      *SECURITY NOTE*: Principals with `dataViewer` on `rls_role_entitlements` can read the entitlement
--      mapping table rows. Keep the table free of sensitive business data, or restrict grants per role.
--
-- 4. BigQuery Editions Compatibility:
--    Row-Level Security requires On-Demand compute or Enterprise / Enterprise Plus reservations
--    (Standard Edition does not support row-level security or subqueries in row access policies;
--    see https://docs.cloud.google.com/bigquery/docs/editions-intro).
-- ==============================================================================


-- ==============================================================================
-- Section 2: Entitlement Lookup Tables in Restricted Security Dataset
-- ==============================================================================
--
-- The security dataset `my-project.security` must be restricted with dataset-level IAM:
-- only authorized Role SAs and security administrators have read access.
--
-- LIMITATION & NESTED RLS INVARIANT:
-- Per official BigQuery documentation (https://docs.cloud.google.com/bigquery/docs/row-level-security-intro):
-- "You cannot apply a row access policy to a table if that table is referenced in a subquery
-- of another row access policy."
-- Therefore, neither `rls_role_entitlements` nor `user_country_map` can have row access policies.

CREATE TABLE IF NOT EXISTS `my-project.security.rls_role_entitlements` (
  role_sa STRING NOT NULL,
  allowed_country STRING NOT NULL
)
OPTIONS (
  description = "Role-to-country entitlement mapping for BigQuery row-level security (unrestricted within security dataset)."
);

-- Seed role entitlements
INSERT INTO `my-project.security.rls_role_entitlements` (role_sa, allowed_country)
VALUES
  ('role-apac@my-project.iam.gserviceaccount.com', 'China'),
  ('role-apac@my-project.iam.gserviceaccount.com', 'Japan'),
  ('role-apac@my-project.iam.gserviceaccount.com', 'South Korea'),
  ('role-apac@my-project.iam.gserviceaccount.com', 'Singapore'),
  ('role-apac@my-project.iam.gserviceaccount.com', 'Australia'),
  ('role-emea@my-project.iam.gserviceaccount.com', 'United Kingdom'),
  ('role-emea@my-project.iam.gserviceaccount.com', 'Germany'),
  ('role-emea@my-project.iam.gserviceaccount.com', 'France'),
  ('role-amer@my-project.iam.gserviceaccount.com', 'United States'),
  ('role-amer@my-project.iam.gserviceaccount.com', 'Brasil');

-- Optional Bridge Table for Pattern 4B (When fact tables lack denormalized country):
-- Stored in `security` dataset WITHOUT row-level security enabled!
CREATE TABLE IF NOT EXISTS `my-project.security.user_country_map` (
  user_id INT64 NOT NULL,
  country STRING NOT NULL
)
OPTIONS (
  description = "Unrestricted lookup bridge mapping user_id to country for Pattern 4B (no RLS enabled)."
);


-- ==============================================================================
-- Section 3: Policy 1 - Legacy ETL & BI Zero-Downtime Bypass (APPLY FIRST)
-- ==============================================================================
--
-- Why Policy 1 must be applied FIRST:
-- BigQuery combines multiple row access policies on the same table using logical OR:
--   effective_filter = (Policy_1_FILTER) OR (Policy_2_FILTER)
--
-- By applying `legacy_etl_bi_bypass` with `FILTER USING (TRUE)` FIRST, existing data pipelines,
-- Looker/Tableau service accounts, and data engineering teams experience ZERO downtime
-- and zero row truncation while the second policy is staged and tested.
--
-- NOTE: In `GRANT TO (...)`, BigQuery accepts:
--   - 'user:email@example.com'
--   - 'serviceAccount:sa@project.iam.gserviceaccount.com'
--   - 'group:group-name@example.com'
--   - 'allAuthenticatedUsers'
-- BigQuery does NOT support wildcard service account domains like 'domain:iam.gserviceaccount.com'.

-- 3.1 Bypass Policy on Dimension Table: users
CREATE OR REPLACE ROW ACCESS POLICY legacy_etl_bi_bypass
ON `my-project.analytics_curated.users`
GRANT TO (
  'group:data-engineering@example.com',
  'group:bi-admins@example.com',
  'serviceAccount:etl-runner@my-project.iam.gserviceaccount.com',
  'serviceAccount:dataplex-scanner@my-project.iam.gserviceaccount.com'
)
FILTER USING (TRUE);

-- 3.2 Bypass Policy on Fact Table: orders
CREATE OR REPLACE ROW ACCESS POLICY legacy_etl_bi_bypass
ON `my-project.analytics_curated.orders`
GRANT TO (
  'group:data-engineering@example.com',
  'group:bi-admins@example.com',
  'serviceAccount:etl-runner@my-project.iam.gserviceaccount.com',
  'serviceAccount:dataplex-scanner@my-project.iam.gserviceaccount.com'
)
FILTER USING (TRUE);

-- 3.3 Bypass Policy on Fact Table: order_items
CREATE OR REPLACE ROW ACCESS POLICY legacy_etl_bi_bypass
ON `my-project.analytics_curated.order_items`
GRANT TO (
  'group:data-engineering@example.com',
  'group:bi-admins@example.com',
  'serviceAccount:etl-runner@my-project.iam.gserviceaccount.com',
  'serviceAccount:dataplex-scanner@my-project.iam.gserviceaccount.com'
)
FILTER USING (TRUE);


-- ==============================================================================
-- Section 4: Policy 2 - Agent Role-SA Filter Across Dimension & Fact Tables
-- ==============================================================================
--
-- Multi-Policy Evaluation:
-- When a Role SA (e.g. `role-apac@...`) queries a table:
--   - `legacy_etl_bi_bypass` evaluates to FALSE (the Role SA is not in the bypass GRANT list).
--   - `agent_role_sa_filter` evaluates the role-scoped predicate.
--   - Result: The Role SA sees strictly the rows permitted by `agent_role_sa_filter`.
--
-- 4.1 Filter Policy on Dimension Table: users
-- `users` contains direct column `country`:
CREATE OR REPLACE ROW ACCESS POLICY agent_role_sa_filter
ON `my-project.analytics_curated.users`
GRANT TO (
  'serviceAccount:role-apac@my-project.iam.gserviceaccount.com',
  'serviceAccount:role-emea@my-project.iam.gserviceaccount.com',
  'serviceAccount:role-amer@my-project.iam.gserviceaccount.com'
)
FILTER USING (
  country IN (
    SELECT allowed_country
    FROM `my-project.security.rls_role_entitlements`
    WHERE role_sa = SESSION_USER()
  )
);

-- ==============================================================================
-- Pattern 4A (Primary Recommended Gold-Mart Pattern — Denormalized `country` on Fact Tables)
-- ==============================================================================
--
-- NESTED RLS INVARIANT:
-- Per official BigQuery documentation (https://docs.cloud.google.com/bigquery/docs/row-level-security-intro),
-- you cannot apply row access policies to tables whose `FILTER USING` subquery references
-- another table that itself has row-level security.
-- Because `analytics_curated.users` has an active row access policy (above), querying `users`
-- inside `orders` or `order_items` RLS predicates is REJECTED by BigQuery.
--
-- In production enterprise gold marts, denormalizing the partitioning/filtering dimension (`country`)
-- onto fact tables (`orders`, `order_items`) is the primary recommended pattern:
--   1. Eliminates nested RLS policy evaluation errors completely.
--   2. Eliminates correlated subquery join latency on every fact query.
--   3. Maintains compatibility with the BigQuery Storage Read API.

-- PREREQUISITE FOR PATTERN 4A:
-- Fact tables (`orders`, `order_items`) must carry a denormalized `country` column populated
-- during ETL/ELT (e.g. `ALTER TABLE ... ADD COLUMN IF NOT EXISTS country STRING` + backfill
-- from `users.country`). If your fact tables do not have `country` and cannot be altered,
-- skip 4.2/4.3 below and apply Pattern 4B instead.

-- 4.2 Primary Pattern 4A on Fact Table: orders
CREATE OR REPLACE ROW ACCESS POLICY agent_role_sa_filter
ON `my-project.analytics_curated.orders`
GRANT TO (
  'serviceAccount:role-apac@my-project.iam.gserviceaccount.com',
  'serviceAccount:role-emea@my-project.iam.gserviceaccount.com',
  'serviceAccount:role-amer@my-project.iam.gserviceaccount.com'
)
FILTER USING (
  country IN (
    SELECT allowed_country
    FROM `my-project.security.rls_role_entitlements`
    WHERE role_sa = SESSION_USER()
  )
);

-- 4.3 Primary Pattern 4A on Fact Table: order_items
CREATE OR REPLACE ROW ACCESS POLICY agent_role_sa_filter
ON `my-project.analytics_curated.order_items`
GRANT TO (
  'serviceAccount:role-apac@my-project.iam.gserviceaccount.com',
  'serviceAccount:role-emea@my-project.iam.gserviceaccount.com',
  'serviceAccount:role-amer@my-project.iam.gserviceaccount.com'
)
FILTER USING (
  country IN (
    SELECT allowed_country
    FROM `my-project.security.rls_role_entitlements`
    WHERE role_sa = SESSION_USER()
  )
);


-- ==============================================================================
-- Pattern 4B (Alternative When Fact Tables Cannot Be Denormalized — Unrestricted Bridge Lookup)
-- ==============================================================================
--
-- If the fact tables cannot be altered with a denormalized `country` column, you CANNOT
-- subquery `analytics_curated.users` (which has RLS).
-- Instead, maintain an unrestricted bridge lookup table in the restricted `security` dataset:
-- `my-project.security.user_country_map (user_id INT64 NOT NULL, country STRING NOT NULL)`.
-- Because `security.user_country_map` has NO row access policies enabled, BigQuery permits
-- subquerying it without triggering nested RLS errors.
--
-- Example Pattern 4B DDL (Alternative):
--
-- CREATE OR REPLACE ROW ACCESS POLICY agent_role_sa_filter
-- ON `my-project.analytics_curated.orders`
-- GRANT TO (
--   'serviceAccount:role-apac@my-project.iam.gserviceaccount.com',
--   'serviceAccount:role-emea@my-project.iam.gserviceaccount.com',
--   'serviceAccount:role-amer@my-project.iam.gserviceaccount.com'
-- )
-- FILTER USING (
--   user_id IN (
--     SELECT m.user_id
--     FROM `my-project.security.user_country_map` AS m
--     INNER JOIN `my-project.security.rls_role_entitlements` AS e
--       ON m.country = e.allowed_country
--     WHERE e.role_sa = SESSION_USER()
--   )
-- );
--
-- CREATE OR REPLACE ROW ACCESS POLICY agent_role_sa_filter
-- ON `my-project.analytics_curated.order_items`
-- GRANT TO (
--   'serviceAccount:role-apac@my-project.iam.gserviceaccount.com',
--   'serviceAccount:role-emea@my-project.iam.gserviceaccount.com',
--   'serviceAccount:role-amer@my-project.iam.gserviceaccount.com'
-- )
-- FILTER USING (
--   user_id IN (
--     SELECT m.user_id
--     FROM `my-project.security.user_country_map` AS m
--     INNER JOIN `my-project.security.rls_role_entitlements` AS e
--       ON m.country = e.allowed_country
--     WHERE e.role_sa = SESSION_USER()
--   )
-- );


-- ==============================================================================
-- Section 5: Safe Rollback & Emergency Tear-Down Order
-- ==============================================================================
--
-- CRITICAL SAFETY INVARIANT:
-- NEVER drop `legacy_etl_bi_bypass` while `agent_role_sa_filter` is still active!
-- Doing so would restrict the entire table to Role SAs only, instantly locking out
-- all ETL pipelines, scheduled queries, Looker dashboards, and human analysts.
--
-- Correct Rollback Order:
-- Step 1: Drop the restrictive agent policy FIRST on all affected tables:
DROP ROW ACCESS POLICY IF EXISTS agent_role_sa_filter ON `my-project.analytics_curated.order_items`;
DROP ROW ACCESS POLICY IF EXISTS agent_role_sa_filter ON `my-project.analytics_curated.orders`;
DROP ROW ACCESS POLICY IF EXISTS agent_role_sa_filter ON `my-project.analytics_curated.users`;

-- Step 2: Once the agent policy is removed, drop the legacy bypass policy:
DROP ROW ACCESS POLICY IF EXISTS legacy_etl_bi_bypass ON `my-project.analytics_curated.order_items`;
DROP ROW ACCESS POLICY IF EXISTS legacy_etl_bi_bypass ON `my-project.analytics_curated.orders`;
DROP ROW ACCESS POLICY IF EXISTS legacy_etl_bi_bypass ON `my-project.analytics_curated.users`;

-- Emergency Option: Drop all row access policies simultaneously on a table:
-- DROP ALL ROW ACCESS POLICIES ON `my-project.analytics_curated.order_items`;
-- DROP ALL ROW ACCESS POLICIES ON `my-project.analytics_curated.orders`;
-- DROP ALL ROW ACCESS POLICIES ON `my-project.analytics_curated.users`;
