# Semantic Analytics Evaluation

This directory contains the native ADK evaluation suite for the V2 semantic
analytics workflow. It tests twelve narrow business questions against an
oracle-authored semantic selection and an exact BigQuery result.

See [`ADK_FLOW.md`](ADK_FLOW.md) for diagrams of the runtime and evaluation
success, recovery, and failure paths.

The suite evaluates twelve cases against canonical semantic contracts in
`config/semantic_contracts/` targeting `bigquery-public-data.thelook_ecommerce`.

## Metrics

- `semantic_selection_match` requires the raw selected context, metric,
  dimension, and relationship IDs to match `gold_cases.yaml` exactly. This is a
  selector-consistency diagnostic, not resolver-level semantic correctness.
- `bigquery_result_match` dry-runs generated SQL, enforces the expected table
  sources and byte limit, executes generated and gold SQL, and compares their
  result rows.

The BigQuery metric executes the generated SQL a second time after the workflow
run. Query caching is enabled, but the evaluation still requires BigQuery
credentials and permissions.

## Environment

Load the project environment and point the workflow at the evaluation
contracts:

```bash
set -a; . ./.env; set +a
export GOOGLE_GENAI_USE_ENTERPRISE=TRUE
export SQL_GENERATOR_MODEL=claude-sonnet-4-5
export SEMANTIC_CONTRACT_PATH="$PWD/config/semantic_contracts"
export EVAL_MAXIMUM_BYTES_BILLED=1000000000
```

`GOOGLE_GENAI_USE_ENTERPRISE=TRUE` is required when `SQL_GENERATOR_MODEL` uses
Claude through Vertex AI. `claude-sonnet-4-5` is the configured default
(`SQL_GENERATOR_MODEL=claude-sonnet-4-5`), which requires enabling Claude Sonnet 4.5
in Model Garden when routing Anthropic via Vertex AI (`GOOGLE_GENAI_USE_ENTERPRISE=TRUE`).
A `404 NOT_FOUND` from the Anthropic publisher endpoint indicates that the project does
not have access to the model; set `SQL_GENERATOR_MODEL` to an enabled model before retrying.
The evaluation reads the public `bigquery-public-data.thelook_ecommerce` tables using
the active project (`BQ_COMPUTE_PROJECT` / `GOOGLE_CLOUD_PROJECT`) for query execution billing.

## Run

Run two cases first and inspect the detailed event trace:

```bash
uv run --extra advanced --extra evaluation adk eval \
  advanced/app/semantic_analytics \
  advanced/app/semantic_analytics/evals/thelook_narrow.evalset.json:completed_orders_total,available_inventory_total \
  --config_file_path advanced/app/semantic_analytics/evals/eval_config.json \
  --print_detailed_results
```

Run the complete suite three times to expose model variance:

```bash
for run in 1 2 3; do
  uv run --extra advanced --extra evaluation adk eval \
    advanced/app/semantic_analytics \
    advanced/app/semantic_analytics/evals/thelook_narrow.evalset.json \
    --config_file_path advanced/app/semantic_analytics/evals/eval_config.json \
    --print_detailed_results
done
```

Each metric has a threshold of `1.0`. A case passes only when both semantic
selection and query results are exact for that run.

See [`results/2026-08-06-sonnet-4-5.md`](results/2026-08-06-sonnet-4-5.md) for
the first three-run baseline.
