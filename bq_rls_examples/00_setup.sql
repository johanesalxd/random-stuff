-- =============================================================================
-- 00_setup.sql
-- Creates a small, generic dataset to demonstrate dynamic BigQuery
-- Row-Level Security (RLS) driven by a mapping/lookup table.
--
-- Scenario (anonymized, generic):
--   A retailer stores transactions in a `sales` fact table. Each row belongs to
--   a store identified by a STRING `store_code` (codes deliberately mix letters
--   and digits, e.g. 'A010', '4079', 'Z014', to mirror real-world ERP org codes
--   that sort lexicographically).
--
--   Which rows a user may see is defined in an `access_map` table as one or more
--   value RANGES per user (low_value .. high_value). The goal is a SINGLE row
--   access policy that evaluates ALL ranges configured for the current user,
--   without hardcoding the number of ranges.
--
-- Placeholders (substituted by run_demo.sh, or replace manually):
--   <PROJECT_ID>     e.g. your-gcp-project
--   <DATASET>        e.g. bq_rls_examples
--   <ADMIN_USER>     a full-access maintainer, e.g. data-admin@example.com
--   <ANALYST_USER>   an end user with restricted access, e.g. analyst@example.com
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS `<PROJECT_ID>.<DATASET>`
OPTIONS (location = 'US');

-- -----------------------------------------------------------------------------
-- Fact table
-- -----------------------------------------------------------------------------
CREATE OR REPLACE TABLE `<PROJECT_ID>.<DATASET>.sales` (
  txn_id     INT64,
  store_code STRING,   -- access-control dimension (STRING => lexicographic order)
  region     STRING,
  product    STRING,
  amount     NUMERIC
);

INSERT INTO `<PROJECT_ID>.<DATASET>.sales`
  (txn_id, store_code, region, product, amount)
VALUES
  (1,  'A010', 'East',  'Widget', 100),
  (2,  'A015', 'East',  'Gadget', 200),
  (3,  'A020', 'East',  'Widget', 150),
  (4,  'A050', 'East',  'Gizmo',  300),
  (5,  '4077', 'West',  'Widget', 120),
  (6,  '4079', 'West',  'Gadget', 220),
  (7,  '4080', 'West',  'Widget',  90),
  (8,  '4085', 'West',  'Gizmo',  410),
  (9,  '4086', 'West',  'Widget',  75),
  (10, '4090', 'West',  'Gadget', 260),
  (11, 'Z014', 'North', 'Widget', 500),
  (12, 'Z015', 'North', 'Gadget', 510),
  (13, 'B100', 'South', 'Widget', 330),
  (14, 'S200', 'South', 'Gizmo',  280);

-- -----------------------------------------------------------------------------
-- Range-based access mapping table (the heart of the dynamic pattern)
-- One row per (user, column, range). A user may have ANY number of ranges.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE TABLE `<PROJECT_ID>.<DATASET>.access_map` (
  email       STRING,
  column_name STRING,
  low_value   STRING,
  high_value  STRING
);

-- The analyst initially gets TWO ranges.
INSERT INTO `<PROJECT_ID>.<DATASET>.access_map`
  (email, column_name, low_value, high_value)
VALUES
  ('<ANALYST_USER>', 'store_code', 'A010', 'A020'),
  ('<ANALYST_USER>', 'store_code', '4077', '4085');

-- -----------------------------------------------------------------------------
-- Discrete allowlist mapping table (for the canonical documented IN-subquery
-- pattern in 02_solution_in_subquery.sql). Use this when access is defined as
-- an explicit list of values rather than ranges.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE TABLE `<PROJECT_ID>.<DATASET>.access_map_discrete` (
  email      STRING,
  store_code STRING
);

INSERT INTO `<PROJECT_ID>.<DATASET>.access_map_discrete`
  (email, store_code)
VALUES
  ('<ANALYST_USER>', 'A010'),
  ('<ANALYST_USER>', '4079');

-- -----------------------------------------------------------------------------
-- Dimension table: the universe of valid store codes.
-- Used by the dynamic RANGE pattern (03) to expand user ranges into a discrete
-- allowlist WITHOUT referencing the fact table inside the policy subquery.
-- A row access policy may NOT contain a correlated subquery that references the
-- target (fact) table, so we correlate against this dimension instead.
-- In a real warehouse this is typically an existing master/dimension table.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE TABLE `<PROJECT_ID>.<DATASET>.store_dim` (
  store_code STRING
);

INSERT INTO `<PROJECT_ID>.<DATASET>.store_dim` (store_code)
VALUES
  ('A010'), ('A015'), ('A020'), ('A050'),
  ('4077'), ('4079'), ('4080'), ('4085'), ('4086'), ('4090'),
  ('Z014'), ('Z015'), ('B100'), ('S200');
