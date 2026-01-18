# Agent Operating Guidelines

This repository contains **FinOps Agents and Cookbooks** for BigQuery. It is not a traditional software project but a collection of prompt engineering artifacts, documentation, and SQL analysis templates.

## 1. Build, Lint, and Test

Since this is a content-based repository, "building" and "testing" refer to validating the agent's logic and output quality.

### Validation Workflow
To "test" changes to the agent logic or prompts:
1.  **Dry Run**: Execute the agent against a known Google Cloud Project (or ask the user for one).
    ```bash
    # Example command to trigger the agent (simulated in chat)
    "Follow the workflow in .agents/commands/optimize_slots.md to analyze project <PROJECT_ID> in <REGION>"
    ```
2.  **Verify Output Generation**:
    - Ensure all expected reports are created in `analysis_results/`.
    - Expected files: `00_current_configuration.md` (optional), `01_slot_metrics.md` through `06_final_recommendation.md`.
3.  **Verify Content Integrity**:
    - Check that SQL queries in `analysis_results/` are syntactically correct.
    - Ensure `bq` CLI commands in `06_final_recommendation.md` are valid and use the correct flags.

### Linting
- **Markdown**: Ensure valid Markdown formatting.
  - Headers should be properly nested (`#`, `##`, `###`).
  - Code blocks must have language tags (e.g., ````sql`, ````bash`, ````markdown`).
- **SQL**: All SQL queries embedded in prompts must be valid BigQuery Standard SQL.

## 2. Code & Style Guidelines

### SQL Style (BigQuery Standard SQL)
- **Keywords**: Use UPPERCASE for all SQL keywords (`SELECT`, `FROM`, `WHERE`, `GROUP BY`, `ORDER BY`).
- **Indentation**: Use **2 spaces** for indentation.
- **Structure**:
  - Place `SELECT`, `FROM`, `WHERE` on their own lines.
  - Field lists should be indented on new lines.
- **Comments**: Use `--` for single-line comments. Provide a source URL or brief explanation for complex logic.

**Example:**
```sql
SELECT
  project_id,
  ROUND(SUM(total_slot_ms) / (1000 * 60 * 60), 1) AS total_slot_hours
FROM
  `region-[YOUR_REGION]`.INFORMATION_SCHEMA.JOBS_BY_PROJECT
WHERE
  job_type = 'QUERY'
GROUP BY
  project_id
ORDER BY
  total_slot_hours DESC;
```

### Markdown Style
- **File Naming**: Use snake_case for filenames (e.g., `optimize_slots.md`).
- **Report Naming**: Use numbered prefixes for ordered reports (e.g., `01_slot_metrics.md`, `02_top_consumers.md`).
- **Frontmatter**: Agent files (`.agents/`) should use YAML frontmatter for metadata.
  ```yaml
  ---
  description: Brief description of the agent or command
  input: required inputs
  output: expected outputs
  ---
  ```

### Naming Conventions
- **Files**: `snake_case` (e.g., `finops_agent.md`).
- **Directories**: `snake_case` (e.g., `analysis_results`, `sample_results`).
- **BigQuery Identifiers**: Follow existing schema (e.g., `INFORMATION_SCHEMA.JOBS_BY_PROJECT`).

### Error Handling & Safety
- **Placeholders**: When writing templates, use clear placeholders like `[YOUR_REGION]` or `<PROJECT_ID>`.
- **Destructive Commands**: The agent should NEVER execute destructive `bq` commands (like `bq rm`) without explicit user confirmation.
- **Fallback Logic**: SQL queries should handle missing fields (e.g., specific edition columns) gracefully or provide fallback queries.

## 3. Agent Behavior
- **Role**: You are an expert BigQuery Administrator and FinOps Analyst.
- **Tone**: Professional, data-driven, and prescriptive.
- **Output**: Prefer structured Markdown tables and bullet points over dense paragraphs.
- **Transparency**: Always explain the "why" behind a recommendation (e.g., "We recommend Autoscaling because your Burst Ratio is > 3.0").
