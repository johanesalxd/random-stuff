-- =============================================================================
-- 99_cleanup.sql
-- Removes everything created by this demo.
--
-- Note: you cannot DROP the *last* row access policy on a table with
-- `DROP ROW ACCESS POLICY`; use `DROP ALL ROW ACCESS POLICIES` instead.
-- Dropping the dataset with CASCADE also removes the tables and their policies.
-- =============================================================================

DROP ALL ROW ACCESS POLICIES ON `<PROJECT_ID>.<DATASET>.sales`;

DROP SCHEMA IF EXISTS `<PROJECT_ID>.<DATASET>` CASCADE;

-- IAM grants made to the analyst by run_demo.sh are revoked by the script
-- (see run_demo.sh teardown), not here.
