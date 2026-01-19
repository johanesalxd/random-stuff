# Agentic Coding Guidelines

This project uses [Dataform](https://dataform.co/) to manage BigQuery datasets, specifically demonstrating Row Level Security (RLS) and Column Level Security (CLS).

## 1. Environment & Tooling

*   **Platform:** Google Cloud BigQuery.
*   **Framework:** Dataform (SQLX).
*   **CLI:** `@dataform/cli` (Node.js).
*   **Configuration:** `workflow_settings.yaml` (Project-level settings and variables).

## 2. Build, Test, and Run Commands

Since this is a Dataform project, "building" implies compiling the SQLX definitions into SQL.

### Core Commands
*   **Compile (Build/Check):**
    ```bash
    dataform compile
    ```
    *Use this to verify syntax and dependency graph validity.*

*   **Dry Run:**
    ```bash
    dataform run --dry-run
    ```
    *Preview the SQL that will be executed without running it.*

*   **Run All:**
    ```bash
    dataform run
    ```
    *Executes the pipeline in BigQuery.*

### Targeted Execution (Run Single Node)
*   **Run a specific table/action:**
    ```bash
    dataform run --actions <node_name>
    ```
    *Example:* `dataform run --actions employees`
    *Example:* `dataform run --actions definitions/models/employees.sqlx`

### Testing & Formatting
*   **Run Tests (Assertions/Unit Tests):**
    ```bash
    dataform test
    ```
*   **Format Code:**
    ```bash
    dataform format
    ```

## 3. Code Style & Conventions

### SQL Style
*   **Keywords:** Use **UPPERCASE** for all SQL keywords (`SELECT`, `FROM`, `WHERE`, `UNION ALL`, `AS`).
*   **Identifiers:** Use **snake_case** for column names and table names (e.g., `employee_id`, `bank_account`).
*   **Indentation:** Use **2 spaces** for indentation.
*   **Commas:** Place commas at the end of the line.

**Example:**
```sqlx
config {
  type: "table",
  name: "example_table"
}

SELECT
  user_id AS id,
  first_name,
  last_name
FROM
  ${ref("source_table")}
WHERE
  status = 'active'
```

### Dataform Configuration (SQLX)
*   **Config Blocks:** Place the `config { ... }` block at the very top of `.sqlx` files.
*   **References:** Always use `${ref("table_name")}` for dependencies to ensure the DAG is built correctly. Never hardcode `project.dataset.table`.
*   **Variables:** Use `dataform.projectConfig.vars.variable_name` to access variables defined in `workflow_settings.yaml`.

### Project Structure
*   **Models:** Place standard tables/views in `definitions/models/`.
*   **Security:** Place RLS/CLS policy definitions in `definitions/security/`.
*   **Documentation:** Add `description: "..."` in the config block for all tables and columns.

## 4. Security & Permissions (Critical)

This project specifically implements security controls.

*   **RLS (Row Level Security):** Implemented via `ROW ACCESS POLICY`.
*   **CLS (Column Level Security):** Implemented via `DATA POLICY` (masking) and explicit `GRANT` statements.
*   **Sensitive Data:**
    *   Respect existing masking policies.
    *   Do not expose sensitive columns (like `ssn`, `salary`, `bank_account`) in new views without appropriate tags or masking.
*   **Principals:** Refer to `workflow_settings.yaml` for defined groups (`admin_group`, `sales_group`).

## 5. Error Handling
*   **Assertions:** Use Dataform assertions (`uniqueKey`, `nonNull`) in the config block to validate data integrity.
    ```javascript
    config {
      type: "table",
      assertions: {
        uniqueKey: ["employee_id"],
        nonNull: ["employee_id", "name"]
      }
    }
    ```
