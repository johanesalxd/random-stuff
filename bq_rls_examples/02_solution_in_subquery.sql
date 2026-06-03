-- =============================================================================
-- 02_solution_in_subquery.sql
-- THE DOCUMENTED PATTERN for DISCRETE allowlists.
--
-- BigQuery row access policies support subqueries against a lookup table. When
-- access is expressed as an explicit list of allowed values (not ranges), a
-- single `IN (SELECT ...)` policy replaces many per-user policies. To change
-- access you simply update the lookup table -- no DDL change.
--
-- This is the exact shape shown in the official docs:
--   https://cloud.google.com/bigquery/docs/managing-row-level-security
--     -> "Create a policy and use a region comparison"
--
-- Note: IN-subquery works for equality/membership. For RANGE-based access,
-- see 03_solution_exists_range.sql.
-- =============================================================================

CREATE OR REPLACE ROW ACCESS POLICY rap_admin_full
ON `<PROJECT_ID>.<DATASET>.sales`
GRANT TO ('user:<ADMIN_USER>')
FILTER USING (TRUE);

CREATE OR REPLACE ROW ACCESS POLICY rap_analyst
ON `<PROJECT_ID>.<DATASET>.sales`
GRANT TO ('user:<ANALYST_USER>')
FILTER USING (
  store_code IN (
    SELECT store_code
    FROM `<PROJECT_ID>.<DATASET>.access_map_discrete`
    WHERE LOWER(email) = LOWER(SESSION_USER())
  )
);
