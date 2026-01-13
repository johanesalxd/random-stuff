# BigQuery RLS and CLS Demo with Dataform

A comprehensive demonstration of BigQuery Row Level Security (RLS) and Column Level Security (CLS) using Dataform, showcasing the new SQL-based data policy approach for column masking and access control.

## Overview

This demo illustrates three types of BigQuery security controls:

1. **Row Level Security (RLS)**: Filter rows based on user identity
2. **Column Level Security - Masking**: Transform sensitive data for unauthorized users
3. **Column Level Security - Access Control**: Block column access entirely

## Two Demo Approaches

This repository includes **two ways** to implement the same RLS/CLS demo:

### 1. SQL-Only Quick Demo (`sql/quick_demo.sql`)
**Best for:** Quick prototyping, learning, ad-hoc testing

- Single SQL file you can copy-paste into BigQuery Console
- No dependencies or setup required
- Immediate execution and testing
- Perfect for experimenting with RLS/CLS before production deployment

**Use this when:** You want to quickly test RLS/CLS concepts or demonstrate to stakeholders.

### 2. Dataform Production Demo (All other files)
**Best for:** Production deployments, CI/CD, version control

- Structured project with separation of concerns
- Environment-specific configuration
- Reusable components and constants
- Integration with Dataform workflows
- Git-based version control

**Use this when:** You're building production data pipelines with proper DevOps practices.

## Demo Scenario

An employee directory with sensitive information where:

- **Admin group** sees all 6 employees (all departments)
- **Sales group** sees only 2 Sales department employees

### Employee Table Schema

| Column | Type | Security |
|--------|------|----------|
| `employee_id` | STRING | Public |
| `name` | STRING | Public |
| `email` | STRING | CLS: Masked (DEFAULT_MASKING_VALUE) |
| `department` | STRING | Used for RLS filtering |
| `salary` | FLOAT64 | CLS: Masked (ALWAYS_NULL) |
| `ssn` | STRING | CLS: Masked (SHA256) |
| `bank_account` | STRING | CLS: Access blocked (RAW_DATA_ACCESS_POLICY) |

### Security Matrix

| Column | Non-Member | Sales Group | Admin Group |
|--------|-----------|-------------|-------------|
| **Rows visible** | 0 | 2 (Sales only) | 6 (All) |
| `email` | ❌ Error | MASKED * | MASKED * |
| `salary` | ❌ Error | MASKED (NULL) * | MASKED (NULL) * |
| `ssn` | ❌ Error | MASKED (SHA256) * | MASKED (SHA256) * |
| `bank_account` | ❌ Error | ❌ Error | ✅ Actual Value |

\* **Known Issue**: See below

## Known Issues

### DATA_MASKING_POLICY Grantees Not Respected

**Issue:** Users with `FINE_GRAINED_READ` grants via SQL `GRANT` statements still see MASKED values instead of ACTUAL values for DATA_MASKING_POLICY columns.

**Verified:**
- ✅ SQL GRANT statements successfully populate the `grantees` field in DATA_POLICY (confirmed via V2 API)
- ✅ RAW_DATA_ACCESS_POLICY works correctly (bank_account column shows actual values for admin)
- ❌ DATA_MASKING_POLICY grantees are NOT being respected (users see masked values despite grants)

**Impact:**
- RLS works as expected
- RAW_DATA_ACCESS_POLICY works as expected
- DATA_MASKING_POLICY applies masking to ALL users regardless of GRANT statements

**Workaround:**
- For columns that need selective access control (not just masking), use RAW_DATA_ACCESS_POLICY
- This blocks access entirely for unauthorized users and shows actual values for granted users

**Status:** This appears to be a limitation or undocumented behavior of SQL-created DATA_POLICY objects. The issue has been documented in the quick_demo.sql file.

## Project Structure

```
bq_rls_cls_dataform/
├── README.md
├── dataform.json                        # Project configuration
├── package.json                         # Dependencies
├── sql/
│   └── quick_demo.sql                   # SOURCE OF TRUTH - SQL-only quick demo
├── includes/
│   ├── constants.js                     # Environment-specific config
│   └── security_config.js               # Group configuration (2 groups)
└── definitions/
    ├── models/
    │   └── employees.sqlx               # Employee table with sample data
    └── security/
        ├── rls_policies.sqlx            # Row access policies (2 policies)
        └── cls_policies.sqlx            # Column masking and access policies (4 policies)
```

## Prerequisites

1. **GCP Project** with BigQuery enabled
2. **Two Google Groups** (create these via Google Admin Console or gcloud CLI):
   - Admin group: `bq-rls-cls-dataform-admin@your-domain.com`
   - Sales group: `bq-rls-cls-dataform-sales@your-domain.com`
3. **For Demo Creator** (you need these to create the policies):
   - `bigquery.dataPolicies.create` - Create data policies
   - `bigquery.rowAccessPolicies.create` - Create row access policies
   - `bigquery.admin` or `bigquery.dataEditor` - Create tables
4. **For Group Members** (they need this to query the table):
   - `bigquery.filteredDataViewer` - Query tables with RLS/CLS
   - `bigquery.jobUser` - Run queries (usually already granted)
5. **Dataform CLI** or Dataform in BigQuery Console
6. **gcloud CLI** installed and authenticated

## Quick Start (SQL-Only Demo)

If you want to test RLS/CLS immediately without any setup:

1. Create the two Google Groups (see Prerequisites)
2. Open BigQuery Console
3. Open the file `sql/quick_demo.sql`
4. Copy-paste sections into BigQuery Console and run sequentially
5. Test with different user accounts

For detailed instructions, see comments in the SQL file.

---

## Production Setup (Dataform Demo)

### 1. Configure Groups

The demo uses two groups configured in `includes/security_config.js`:

```javascript
const groups = {
  admin: "group:bq-rls-cls-dataform-admin@johanesa.altostrat.com",
  sales: "group:bq-rls-cls-dataform-sales@johanesa.altostrat.com"
};
```

Update these to match your environment.

### 2. Create Google Groups

Create the two groups via Google Admin Console or gcloud:

```bash
gcloud identity groups create bq-rls-cls-dataform-admin@johanesa.altostrat.com \
  --organization="YOUR_ORG_ID" \
  --display-name="BigQuery RLS/CLS Demo - Admin Group"

gcloud identity groups create bq-rls-cls-dataform-sales@johanesa.altostrat.com \
  --organization="YOUR_ORG_ID" \
  --display-name="BigQuery RLS/CLS Demo - Sales Group"
```

### 3. Add Group Members

Add test users to each group via Cloud Console:
1. Go to [Google Admin Console](https://admin.google.com)
2. Navigate to Directory > Groups
3. Add members to each group

**Note:** Group members need `bigquery.filteredDataViewer` and `bigquery.jobUser` roles to query the table. These are typically granted at the project level.

### 4. Deploy Dataform Project

**Option A: Using Dataform CLI**

```bash
# Install dependencies
npm install

# Compile and run
dataform compile
dataform run
```

**Option B: Using BigQuery Console**

1. Go to BigQuery > Dataform
2. Create a new repository
3. Link to this directory
4. Click "Execute" to run all definitions

### 5. Verify Deployment

Check that resources were created:

```bash
# List row access policies
bq ls --row_access_policies --format=prettyjson johanesa-playground-326616:demo_dataset.employees

# View employee table (via BigQuery Console or bq CLI)
bq query --use_legacy_sql=false \
  "SELECT employee_id, name, email, department, salary, ssn FROM \`johanesa-playground-326616.demo_dataset.employees\`"
```

**Note:** BigQuery doesn't have an INFORMATION_SCHEMA view for row access policies. Use the `bq ls` command or check the table details in BigQuery Console UI.

## Testing the Demo

### Test RLS (Row Filtering)

**As Sales group member:**
```sql
-- Note: Cannot use SELECT * because Sales doesn't have access to bank_account column
SELECT
  employee_id,
  name,
  email,
  department,
  salary,
  ssn
FROM `johanesa-playground-326616.demo_dataset.employees`;
-- Returns only 2 rows (E001, E002 - Sales department)
```

**As Admin group member:**
```sql
SELECT * FROM `johanesa-playground-326616.demo_dataset.employees`;
-- Returns all 6 rows (E001-E006 - All departments)
-- Works because Admin has access to all columns including bank_account
```

### Test CLS Masking

**As Sales group member:**
```sql
SELECT
  employee_id,
  name,
  email,        -- Shows "" (masked - known issue)
  salary,       -- Shows NULL (masked - known issue)
  ssn           -- Shows SHA256 hash (masked - known issue)
FROM `johanesa-playground-326616.demo_dataset.employees`;
-- Returns 2 rows with masked values
```

**As Admin group member:**
```sql
SELECT
  employee_id,
  name,
  email,        -- Shows "" (masked - known issue)
  salary,       -- Shows NULL (masked - known issue)
  ssn,          -- Shows SHA256 hash (masked - known issue)
  bank_account  -- Shows actual value (RAW_DATA_ACCESS_POLICY works!)
FROM `johanesa-playground-326616.demo_dataset.employees`;
-- Returns 6 rows with masked values except bank_account
```

### Test Raw Data Access Policy

**As Sales group member:**
```sql
SELECT bank_account FROM `johanesa-playground-326616.demo_dataset.employees`;
-- Error: Access Denied - User does not have permission
```

**As Admin group member:**
```sql
SELECT bank_account FROM `johanesa-playground-326616.demo_dataset.employees`;
-- Success: Shows actual bank account numbers (9876543210, etc.)
```

## Key Concepts

### Row Level Security (RLS)

RLS filters rows based on the authenticated user's identity:

```sql
CREATE OR REPLACE ROW ACCESS POLICY sales_department_access
ON `project.dataset.employees`
GRANT TO ('group:sales@domain.com')
FILTER USING (department = 'Sales');
```

### Column Level Security - Masking

Transforms data for unauthorized users using predefined rules:

```sql
-- Step 1: Create DATA_POLICY
CREATE OR REPLACE DATA_POLICY `project.region-us.ssn_masking_policy`
OPTIONS (
  data_policy_type="DATA_MASKING_POLICY",
  masking_expression="SHA256"
);

-- Step 2: Attach to column
ALTER TABLE `project.dataset.employees`
ALTER COLUMN ssn SET OPTIONS (
  data_policies = ["{'name':'project.region-us.ssn_masking_policy'}"]
);

-- Step 3: Grant access (currently not working as expected)
GRANT FINE_GRAINED_READ
ON DATA_POLICY `project.region-us.ssn_masking_policy`
TO "principalSet://goog/group/admin@domain.com";
```

**Available Masking Rules:**
- `SHA256` - Hash the value
- `ALWAYS_NULL` - Return NULL
- `DEFAULT_MASKING_VALUE` - Return type-specific default
- `LAST_FOUR_CHARACTERS` - Show only last 4 characters

### Column Level Security - Access Control

Blocks access to columns entirely using raw data access policy:

```sql
CREATE OR REPLACE DATA_POLICY `project.region-us.bank_account_access_policy`
OPTIONS (
  data_policy_type="RAW_DATA_ACCESS_POLICY"
);

ALTER TABLE `project.dataset.employees`
ALTER COLUMN bank_account SET OPTIONS (
  data_policies = ["{'name':'project.region-us.bank_account_access_policy'}"]
);

GRANT FINE_GRAINED_READ
ON DATA_POLICY `project.region-us.bank_account_access_policy`
TO "principalSet://goog/group/admin@domain.com";
```

## Dataform Implementation Patterns

### Using Operations for Security Policies

Security policies are implemented as `type: "operations"`:

```javascript
config {
  type: "operations",
  name: "rls_policies",
  hasOutput: false,
  dependencies: ["employees"]
}
```

This ensures:
- Policies execute after table creation
- Clear separation of concerns
- Independent policy management

### Environment Configuration

Use `includes/constants.js` for environment-specific values:

```javascript
const config = envConfig[currentEnv];
module.exports = {
  project: config.project,
  dataset: config.dataset,
  location: config.location,
  region: `region-${config.location}`
};
```

Switch environments via `dataform.json`:

```json
{
  "vars": {
    "env": "prod"
  }
}
```

## Troubleshooting

### Error: Permission denied

Ensure users have `bigquery.filteredDataViewer` role:

```bash
gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="group:GROUP@DOMAIN.com" \
  --role="roles/bigquery.filteredDataViewer"
```

### Error: Data policy not found

Verify the location matches your dataset region:

```sql
SELECT location FROM `project.dataset.INFORMATION_SCHEMA.SCHEMATA`
WHERE schema_name = 'demo_dataset';
```

### Policies not applying

Check policy existence:

```sql
-- Row access policies
SELECT * FROM `project.dataset.INFORMATION_SCHEMA.ROW_ACCESS_POLICIES`
WHERE table_name = 'employees';
```

### Verifying DATA_POLICY Grantees

Use the V2 API to check if GRANT statements populated the grantees field:

```bash
ACCESS_TOKEN=$(gcloud auth print-access-token)
curl -s -X GET \
  "https://bigquerydatapolicy.googleapis.com/v2/projects/johanesa-playground-326616/locations/us/dataPolicies/ssn_masking_policy" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" | jq '.grantees'
```

## Best Practices

1. **Separation of Concerns**: Keep security policies in separate operation files
2. **Environment Management**: Use constants for project/dataset/location
3. **Group-Based Access**: Use groups instead of individual users
4. **Least Privilege**: Grant minimal necessary access
5. **Documentation**: Comment all security policies with business justification
6. **Testing**: Test with actual group members before production deployment
7. **Monitoring**: Monitor policy usage with BigQuery audit logs
8. **Use RAW_DATA_ACCESS_POLICY**: For selective column access control, prefer RAW_DATA_ACCESS_POLICY over DATA_MASKING_POLICY

## Resources

- [BigQuery Row Level Security](https://cloud.google.com/bigquery/docs/row-level-security-intro)
- [BigQuery Column Level Security](https://cloud.google.com/bigquery/docs/column-level-security-intro)
- [Data Policies on Columns](https://cloud.google.com/bigquery/docs/column-data-masking#data-policies-on-column)
- [Dataform Documentation](https://cloud.google.com/dataform/docs)
- [BigQuery IAM Roles](https://cloud.google.com/bigquery/docs/access-control)

## License

This demo is provided as-is for educational purposes.
