-- ================================================================
-- BigQuery RLS & CLS Quick Demo - SQL-Only Version
-- ================================================================
-- This demo shows Row Level Security and Column Level Security
-- using the new SQL-based data policy approach (no policy tags needed)
--
-- BEFORE RUNNING:
-- 1. Create two Google Groups:
--    - Admin group: bq-rls-cls-dataform-admin@johanesa.altostrat.com
--    - Sales group: bq-rls-cls-dataform-sales@johanesa.altostrat.com
-- 2. Make sure you have the necessary IAM permissions
-- 3. Grant yourself the necessary roles to create policies
-- ================================================================

-- ================================================================
-- STEP 1: Create Dataset
-- ================================================================

CREATE SCHEMA IF NOT EXISTS `johanesa-playground-326616.demo_dataset`
OPTIONS(location="us");


-- ================================================================
-- STEP 2: Create Employee Table with Sample Data
-- ================================================================

CREATE OR REPLACE TABLE `johanesa-playground-326616.demo_dataset.employees` (
  employee_id STRING,
  name STRING,
  email STRING,
  department STRING,
  salary FLOAT64,
  ssn STRING,
  bank_account STRING
);

INSERT INTO `johanesa-playground-326616.demo_dataset.employees` VALUES
  ('E001', 'Alice Johnson', 'alice.johnson@company.com', 'Sales', 75000.0, '123-45-6789', '9876543210'),
  ('E002', 'Bob Smith', 'bob.smith@company.com', 'Sales', 68000.0, '234-56-7890', '8765432109'),
  ('E003', 'Carol Williams', 'carol.williams@company.com', 'HR', 82000.0, '345-67-8901', '7654321098'),
  ('E004', 'David Brown', 'david.brown@company.com', 'HR', 79000.0, '456-78-9012', '6543210987'),
  ('E005', 'Emma Davis', 'emma.davis@company.com', 'Finance', 95000.0, '567-89-0123', '5432109876'),
  ('E006', 'Frank Miller', 'frank.miller@company.com', 'Finance', 88000.0, '678-90-1234', '4321098765');


-- ================================================================
-- STEP 3: Create Column Level Security (CLS) Policies
-- ================================================================

-- ------------------------------------------------------------
-- CLS Policy 1: Mask SSN with SHA256
-- ------------------------------------------------------------

-- Step 3a: Create the data masking policy
CREATE OR REPLACE DATA_POLICY `johanesa-playground-326616.region-us.ssn_masking_policy`
OPTIONS (
  data_policy_type="DATA_MASKING_POLICY",
  masking_expression="SHA256"
);

-- Step 3b: Attach the policy to the column
ALTER TABLE `johanesa-playground-326616.demo_dataset.employees`
ALTER COLUMN ssn SET OPTIONS (
  data_policies = ["{'name':'johanesa-playground-326616.region-us.ssn_masking_policy'}"]
);

-- Step 3c: Grant unmasked access to ADMIN and SALES groups
GRANT FINE_GRAINED_READ
ON DATA_POLICY `johanesa-playground-326616.region-us.ssn_masking_policy`
TO "principalSet://goog/group/bq-rls-cls-dataform-admin@johanesa.altostrat.com";

GRANT FINE_GRAINED_READ
ON DATA_POLICY `johanesa-playground-326616.region-us.ssn_masking_policy`
TO "principalSet://goog/group/bq-rls-cls-dataform-sales@johanesa.altostrat.com";


-- ------------------------------------------------------------
-- CLS Policy 2: Mask email with default masking value
-- ------------------------------------------------------------

CREATE OR REPLACE DATA_POLICY `johanesa-playground-326616.region-us.email_masking_policy`
OPTIONS (
  data_policy_type="DATA_MASKING_POLICY",
  masking_expression="DEFAULT_MASKING_VALUE"
);

ALTER TABLE `johanesa-playground-326616.demo_dataset.employees`
ALTER COLUMN email SET OPTIONS (
  data_policies = ["{'name':'johanesa-playground-326616.region-us.email_masking_policy'}"]
);

GRANT FINE_GRAINED_READ
ON DATA_POLICY `johanesa-playground-326616.region-us.email_masking_policy`
TO "principalSet://goog/group/bq-rls-cls-dataform-admin@johanesa.altostrat.com";

GRANT FINE_GRAINED_READ
ON DATA_POLICY `johanesa-playground-326616.region-us.email_masking_policy`
TO "principalSet://goog/group/bq-rls-cls-dataform-sales@johanesa.altostrat.com";


-- ------------------------------------------------------------
-- CLS Policy 3: Hide salary as NULL
-- ------------------------------------------------------------

CREATE OR REPLACE DATA_POLICY `johanesa-playground-326616.region-us.salary_masking_policy`
OPTIONS (
  data_policy_type="DATA_MASKING_POLICY",
  masking_expression="ALWAYS_NULL"
);

ALTER TABLE `johanesa-playground-326616.demo_dataset.employees`
ALTER COLUMN salary SET OPTIONS (
  data_policies = ["{'name':'johanesa-playground-326616.region-us.salary_masking_policy'}"]
);

GRANT FINE_GRAINED_READ
ON DATA_POLICY `johanesa-playground-326616.region-us.salary_masking_policy`
TO "principalSet://goog/group/bq-rls-cls-dataform-admin@johanesa.altostrat.com";

GRANT FINE_GRAINED_READ
ON DATA_POLICY `johanesa-playground-326616.region-us.salary_masking_policy`
TO "principalSet://goog/group/bq-rls-cls-dataform-sales@johanesa.altostrat.com";


-- ------------------------------------------------------------
-- CLS Policy 4: RAW ACCESS POLICY - Block access to bank_account entirely
-- ------------------------------------------------------------

CREATE OR REPLACE DATA_POLICY `johanesa-playground-326616.region-us.bank_account_access_policy`
OPTIONS (
  data_policy_type="RAW_DATA_ACCESS_POLICY"
);

ALTER TABLE `johanesa-playground-326616.demo_dataset.employees`
ALTER COLUMN bank_account SET OPTIONS (
  data_policies = ["{'name':'johanesa-playground-326616.region-us.bank_account_access_policy'}"]
);

-- Grant access to ADMIN group only (only they can query this column)
GRANT FINE_GRAINED_READ
ON DATA_POLICY `johanesa-playground-326616.region-us.bank_account_access_policy`
TO "principalSet://goog/group/bq-rls-cls-dataform-admin@johanesa.altostrat.com";

-- NOTE: RAW_DATA_ACCESS_POLICY blocks access entirely for unauthorized users
-- In production, you'd want only finance team:
-- GRANT FINE_GRAINED_READ ON DATA_POLICY `...bank_account_access_policy` TO "principalSet://goog/group/finance-team@domain.com";


-- ================================================================
-- STEP 4: Create Row Level Security (RLS) Policies
-- ================================================================

-- ------------------------------------------------------------
-- RLS Policy 1: Admin sees ALL rows
-- ------------------------------------------------------------

CREATE OR REPLACE ROW ACCESS POLICY admin_full_access
ON `johanesa-playground-326616.demo_dataset.employees`
GRANT TO ('group:bq-rls-cls-dataform-admin@johanesa.altostrat.com')
FILTER USING (TRUE);


-- ------------------------------------------------------------
-- RLS Policy 2: Sales group sees only Sales department
-- ------------------------------------------------------------

CREATE OR REPLACE ROW ACCESS POLICY sales_department_access
ON `johanesa-playground-326616.demo_dataset.employees`
GRANT TO ('group:bq-rls-cls-dataform-sales@johanesa.altostrat.com')
FILTER USING (department = 'Sales');


-- ================================================================
-- STEP 5: Verify Policies Were Created
-- ================================================================

-- NOTE: INFORMATION_SCHEMA queries for policies are not readily available
-- via standard SQL queries in the current BigQuery API.
-- Instead, verify policies by testing the actual data queries below.

-- The best way to verify is to query the data and observe the masking behavior:
SELECT
  employee_id,
  name,
  email,        -- Should be masked (empty string)
  department,
  salary,       -- Should be NULL
  ssn           -- Should be SHA256 hash
FROM `johanesa-playground-326616.demo_dataset.employees`
LIMIT 10;

-- Verify RAW_DATA_ACCESS_POLICY blocks access entirely:
-- This query should FAIL with "Access Denied" error for unauthorized users:
-- SELECT employee_id, bank_account FROM `johanesa-playground-326616.demo_dataset.employees`;


-- ================================================================
-- STEP 6: Test Queries (3 Persona Scenarios)
-- ================================================================

-- ┌────────────────────────────────────────────────────────────────┐
-- │ Test Matrix Summary                                            │
-- ├─────────────┬──────────┬────────┬─────────┬─────────┬─────────┤
-- │ User Type   │ Group    │ Rows   │ email   │ salary  │ ssn     │
-- ├─────────────┼──────────┼────────┼─────────┼─────────┼─────────┤
-- │ Non-member  │ None     │ 0      │ N/A     │ N/A     │ N/A     │
-- │ Sales       │ sales@   │ 2      │ MASKED  │ MASKED  │ MASKED  │
-- │ Admin       │ admin@   │ 6      │ MASKED  │ MASKED  │ MASKED  │
-- └─────────────┴──────────┴────────┴─────────┴─────────┴─────────┘

-- ⚠️ KNOWN ISSUE: DATA_MASKING_POLICY grantees not being respected
--
-- The SQL GRANT statements successfully populate the 'grantees' field in the
-- DATA_POLICY resource (verified via V2 API), but users in the grantees list
-- still see MASKED values instead of ACTUAL values.
--
-- Verified:
--   ✓ SQL GRANT populates DATA_POLICY.grantees field correctly
--   ✓ Grantees include: admin user + both groups (verified via API)
--   ✓ RAW_DATA_ACCESS_POLICY works correctly (bank_account column)
--   ✗ DATA_MASKING_POLICY grantees are NOT being respected
--
-- This appears to be a limitation or undocumented behavior of SQL-created
-- DATA_POLICY objects. Users with FINE_GRAINED_READ grants via SQL GRANT
-- still see masked values.


-- ------------------------------------------------------------
-- Test 1: Non-Member (NOT in any group)
-- Expected Results:
--   - RLS: 0 rows (no row access policy grants this user)
--   - CLS: Protected columns get ACCESS DENIED (no FINE_GRAINED_READ grant)
--   - Note: Must query ONLY unprotected columns to see RLS behavior
-- ------------------------------------------------------------

SELECT
  employee_id,
  name,
  department  -- Only unprotected columns
FROM `johanesa-playground-326616.demo_dataset.employees`;
-- Expected: 0 rows returned (RLS filters all rows)

-- If you try to query protected columns (email, salary, ssn), you'll get:
-- "Access Denied: User does not have masked access or raw data access to protected columns"
-- This is because CLS validation happens BEFORE RLS filtering


-- ------------------------------------------------------------
-- Test 2: Sales Group Member (NOT Admin)
-- Expected Results:
--   - RLS: 2 rows (Sales department only: Alice, Bob)
--   - CLS:
--     * email → "" (MASKED - grantees not respected)
--     * salary → NULL (MASKED - grantees not respected)
--     * ssn → SHA256 hash (MASKED - grantees not respected)
--     * bank_account → ACCESS DENIED (RAW_DATA_ACCESS_POLICY - NO grant)
-- ------------------------------------------------------------

SELECT
  employee_id,
  name,
  email,        -- Shows: "" (masked despite grant)
  department,
  salary,       -- Shows: NULL (masked despite grant)
  ssn           -- Shows: SHA256 hash (masked despite grant)
FROM `johanesa-playground-326616.demo_dataset.employees`;
-- Expected: 2 rows (E001, E002) with MASKED values

-- This query will FAIL with ACCESS DENIED error (bank_account has no grant):
-- SELECT employee_id, bank_account FROM `johanesa-playground-326616.demo_dataset.employees`;


-- ------------------------------------------------------------
-- Test 3: Admin Group Member
-- Expected Results:
--   - RLS: 6 rows (ALL departments via FILTER USING (TRUE))
--   - CLS:
--     * email → "" (MASKED - grantees not respected)
--     * salary → NULL (MASKED - grantees not respected)
--     * ssn → SHA256 hash (MASKED - grantees not respected)
--     * bank_account → "9876543210" (ACTUAL - RAW_DATA_ACCESS_POLICY works!)
-- ------------------------------------------------------------

SELECT
  employee_id,
  name,
  email,        -- Shows: "" (masked despite grant)
  department,
  salary,       -- Shows: NULL (masked despite grant)
  ssn,          -- Shows: SHA256 hash (masked despite grant)
  bank_account  -- Shows: 9876543210 (actual - RAW_DATA_ACCESS_POLICY works)
FROM `johanesa-playground-326616.demo_dataset.employees`;
-- Expected: 6 rows (E001-E006) with masked values except bank_account


-- ================================================================
-- STEP 7: Clean Up (Optional - removes all policies and data)
-- ================================================================

-- Remove RLS Policies
-- DROP ROW ACCESS POLICY admin_full_access ON `johanesa-playground-326616.demo_dataset.employees`;
-- DROP ROW ACCESS POLICY sales_department_access ON `johanesa-playground-326616.demo_dataset.employees`;

-- Remove CLS Policies
-- DROP DATA_POLICY `johanesa-playground-326616.region-us.ssn_masking_policy`;
-- DROP DATA_POLICY `johanesa-playground-326616.region-us.email_masking_policy`;
-- DROP DATA_POLICY `johanesa-playground-326616.region-us.salary_masking_policy`;
-- DROP DATA_POLICY `johanesa-playground-326616.region-us.bank_account_access_policy`;

-- Remove Table and Dataset
-- DROP TABLE `johanesa-playground-326616.demo_dataset.employees`;
-- DROP SCHEMA `johanesa-playground-326616.demo_dataset`;


-- ================================================================
-- NOTES
-- ================================================================

-- SQL-Based DATA_POLICY Access Control:
--   For SQL-based policies (this approach), access is controlled by SQL GRANT statements:
--
--   GRANT FINE_GRAINED_READ ON DATA_POLICY ... TO "principalSet://goog/group/..."
--     → User sees ACTUAL values for that column
--
--   No GRANT
--     → User gets ACCESS DENIED (cannot query the column)
--
--   Note: IAM roles like maskedReader/fineGrainedReader are for the older
--   policy tag-based approach. For SQL-based DATA_POLICY, the SQL GRANT is
--   the primary and sufficient access control mechanism.

-- Available Masking Rules:
--   - SHA256: Hash the value
--   - ALWAYS_NULL: Return NULL
--   - DEFAULT_MASKING_VALUE: Return type-specific default (e.g., empty string, 0)
--   - LAST_FOUR_CHARACTERS: Show only last 4 characters

-- Difference between Masking and Raw Access Policy:
--   - DATA_MASKING_POLICY: Defines transformation rules (SHA256, NULL, etc.)
--     Users with FINE_GRAINED_READ grant see actual values
--     Users without grant get ACCESS DENIED
--   - RAW_DATA_ACCESS_POLICY: Blocks column access entirely for unauthorized users
--     Users with FINE_GRAINED_READ grant can query the column
--     Users without grant get ACCESS DENIED

-- Required IAM Permissions (for creating policies):
--   - bigquery.dataPolicies.create
--   - bigquery.rowAccessPolicies.create
--   - bigquery.tables.create

-- Verifying Grantees via V2 API:
--   Check if SQL GRANT populated the grantees field:
--
--   ACCESS_TOKEN=$(gcloud auth print-access-token)
--   curl -s -X GET \
--     "https://bigquerydatapolicy.googleapis.com/v2/projects/PROJECT/locations/LOCATION/dataPolicies/POLICY_ID" \
--     -H "Authorization: Bearer ${ACCESS_TOKEN}" | jq '.grantees'
--
--   Example:
--   curl -s -X GET \
--     "https://bigquerydatapolicy.googleapis.com/v2/projects/johanesa-playground-326616/locations/us/dataPolicies/ssn_masking_policy" \
--     -H "Authorization: Bearer $(gcloud auth print-access-token)" | jq '.grantees'

-- Testing Tips:
--   1. Run queries in incognito mode or different browser profiles
--   2. Use gcloud auth login to switch between test users
--   3. Check the actual user with: SELECT SESSION_USER();
--   4. Verify group membership propagation (can take 5-15 minutes)
--   5. Verify grantees via V2 API (see commands above)
