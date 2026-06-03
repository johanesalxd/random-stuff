-- =============================================================================
-- 01_current_approach_hardcoded.sql
-- THE "BEFORE": the common but NON-SCALABLE pattern.
--
-- Each access range is hardcoded into the policy using a positional subquery
-- (ORDER BY ... LIMIT 1 OFFSET n) for the low and high bound, OR-ed together.
-- This works, but the number of OR blocks must match the number of ranges a
-- user has. Add a new range to access_map and this policy SILENTLY misses it
-- until you manually edit the DDL to add another OR block.
--
-- This file hardcodes exactly TWO rules (OFFSET 0 and OFFSET 1).
-- =============================================================================

-- Full-access policy for the maintainer/admin. When ANY policy exists on a
-- table, users not covered by a policy see ZERO rows -- so admins need an
-- explicit TRUE filter to retain full access.
CREATE OR REPLACE ROW ACCESS POLICY rap_admin_full
ON `<PROJECT_ID>.<DATASET>.sales`
GRANT TO ('user:<ADMIN_USER>')
FILTER USING (TRUE);

-- Restricted policy for the analyst, hardcoded to 2 ranges.
CREATE OR REPLACE ROW ACCESS POLICY rap_analyst
ON `<PROJECT_ID>.<DATASET>.sales`
GRANT TO ('user:<ANALYST_USER>')
FILTER USING (
  -- Rule 1 (the lexicographically-first range, OFFSET 0)
  store_code BETWEEN
    (
      SELECT low_value
      FROM `<PROJECT_ID>.<DATASET>.access_map`
      WHERE LOWER(email) = LOWER(SESSION_USER())
        AND column_name = 'store_code'
      ORDER BY low_value
      LIMIT 1 OFFSET 0
    )
    AND
    (
      SELECT high_value
      FROM `<PROJECT_ID>.<DATASET>.access_map`
      WHERE LOWER(email) = LOWER(SESSION_USER())
        AND column_name = 'store_code'
      ORDER BY low_value
      LIMIT 1 OFFSET 0
    )

  OR

  -- Rule 2 (the next range, OFFSET 1)
  store_code BETWEEN
    (
      SELECT low_value
      FROM `<PROJECT_ID>.<DATASET>.access_map`
      WHERE LOWER(email) = LOWER(SESSION_USER())
        AND column_name = 'store_code'
      ORDER BY low_value
      LIMIT 1 OFFSET 1
    )
    AND
    (
      SELECT high_value
      FROM `<PROJECT_ID>.<DATASET>.access_map`
      WHERE LOWER(email) = LOWER(SESSION_USER())
        AND column_name = 'store_code'
      ORDER BY low_value
      LIMIT 1 OFFSET 1
    )

  -- A third range would require a third OR block here, and so on...
);
