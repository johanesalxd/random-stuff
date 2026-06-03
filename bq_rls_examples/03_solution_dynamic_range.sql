-- =============================================================================
-- 03_solution_dynamic_range.sql
-- THE "AFTER": the recommended DYNAMIC, RANGE-based pattern that ACTUALLY WORKS
-- in BigQuery row access policies.
--
-- IMPORTANT BigQuery limitation (verified):
--   A row access policy filter may NOT contain a correlated subquery that
--   references the target (fact) table. The intuitive form
--       EXISTS (SELECT 1 FROM access_map m
--               WHERE ... AND sales.store_code BETWEEN m.low_value AND m.high_value)
--   fails with:
--       "Row access policy ... may not include correlated subqueries
--        involving target table."
--   Also, the target-table column must be referenced UNQUALIFIED (no `sales.`).
--
-- WORKAROUND (scalable and dynamic):
--   Expand each user's ranges into a discrete allowlist of codes by JOINing the
--   range mapping table (access_map) against a DIMENSION table of all valid
--   codes (store_dim). That subquery references only lookup/dimension tables --
--   NOT the target table -- so it is allowed. The outer filter is then a simple
--   membership test on the (unqualified) target column.
--
-- This evaluates ALL ranges a user has, with NO hardcoding. To change access you
-- only INSERT/DELETE rows in access_map -- no DDL changes to the policy.
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
    SELECT d.store_code
    FROM `<PROJECT_ID>.<DATASET>.store_dim` AS d
    JOIN `<PROJECT_ID>.<DATASET>.access_map` AS m
      ON  LOWER(m.email) = LOWER(SESSION_USER())
      AND m.column_name  = 'store_code'
      AND d.store_code BETWEEN m.low_value AND m.high_value
  )
);
