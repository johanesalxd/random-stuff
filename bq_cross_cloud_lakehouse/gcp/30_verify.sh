#!/usr/bin/env bash
# Wait until both federated Froyo tables are queryable and nonempty.
set -euo pipefail
cd "$(dirname "$0")/.."
source ./config.local.env

gcloud alpha biglake iceberg catalogs describe "${FEDERATED_CATALOG}" \
  --project="${GCP_PROJECT}"

for attempt in $(seq 1 12); do
  all_ready="true"
  for table in "${FROYO_LOYALTY_TABLE}" "${FROYO_SALES_TABLE}"; do
    fqtn="${GCP_PROJECT}.${FEDERATED_CATALOG}.${GLUE_DATABASE}.${table}"
    if query_json="$(bq --location="${GCP_REGION}" \
        --project_id="${GCP_PROJECT}" --format=json query \
        --use_legacy_sql=false \
        "SELECT COUNT(*) AS row_count FROM \`${fqtn}\`" 2>/dev/null)"; then
      row_count="$(QUERY_JSON="${query_json}" python3 -c \
        'import json,os; print(json.loads(os.environ["QUERY_JSON"])[0]["row_count"])')"
      if ((row_count > 0)); then
        echo "  ${fqtn}: ${row_count} rows"
      else
        all_ready="false"
      fi
    else
      all_ready="false"
    fi
  done

  if [[ "${all_ready}" == "true" ]]; then
    echo "Federation verification passed."
    exit 0
  fi
  echo "  [$((attempt * 10))s] waiting for metadata refresh"
  sleep 10
done

echo "ERROR: Federated tables were not queryable after two minutes." >&2
exit 1
