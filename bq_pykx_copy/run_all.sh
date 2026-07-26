#!/bin/bash
#
# Run the full kdb+ -> Parquet -> BigQuery PoC end to end.
#
# Prerequisites:
#   * `uv sync` has been run
#   * .env is filled and a valid kc.lic is present (licensed PyKX)
#   * `gcloud auth application-default login` has been done

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly SCRIPT_DIR

#######################################
# Run one pipeline step via uv.
# Arguments:
#   $1 - human-readable step label
#   $2 - python script filename
#######################################
run_step() {
  local label="$1"
  local script="$2"
  echo "== ${label} ==" >&2
  uv run python "${SCRIPT_DIR}/${script}"
}

main() {
  run_step "0. generate synthetic HDB" "00_generate_synthetic_hdb.py"
  run_step "1. kdb+ -> parquet (chunked)" "01_kdb_to_parquet.py"
  run_step "2. upload to GCS + load BigQuery" "02_load_bigquery.py"
  run_step "3. validate round-trip" "03_validate.py"
  echo "== done ==" >&2
}

main "$@"
