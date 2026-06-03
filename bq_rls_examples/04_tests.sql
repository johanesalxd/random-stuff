-- =============================================================================
-- 04_tests.sql
-- Verification queries. These are plain SELECTs; the row access policy in force
-- (applied by 01/02/03) determines what each running identity actually sees.
--
-- run_demo.sh executes the relevant queries below as <ADMIN_USER> and as
-- <ANALYST_USER> after each policy is applied. You can also run them manually.
-- =============================================================================

-- (1) What identity am I, and what does the table look like FROM MY PERSPECTIVE?
--     Run as <ADMIN_USER>  -> 14 rows (TRUE filter).
--     Run as <ANALYST_USER> -> only rows inside the user's mapped range(s).
SELECT SESSION_USER() AS running_as;

SELECT txn_id, store_code, region, product, amount
FROM `<PROJECT_ID>.<DATASET>.sales`
ORDER BY txn_id;

SELECT COUNT(*) AS visible_rows
FROM `<PROJECT_ID>.<DATASET>.sales`;

-- (2) LOGIC-EQUIVALENCE CHECK (no RLS involved).
--     Proves what the EXISTS+BETWEEN policy *should* return for a given user by
--     simulating SESSION_USER() with a literal email. Useful for unit-testing
--     the mapping logic independently of who is running the query.
--     Replace <ANALYST_USER> below if you want to check a different user.
SELECT s.txn_id, s.store_code, s.region, s.product, s.amount
FROM `<PROJECT_ID>.<DATASET>.sales` AS s
WHERE EXISTS (
  SELECT 1
  FROM `<PROJECT_ID>.<DATASET>.access_map` AS m
  WHERE LOWER(m.email) = LOWER('<ANALYST_USER>')
    AND m.column_name = 'store_code'
    AND s.store_code BETWEEN m.low_value AND m.high_value
)
ORDER BY s.txn_id;
