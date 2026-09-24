#!/usr/bin/env bash
# ==============================================================================
# SGX Google Cloud Data Contracts - Clean Infrastructure Teardown
# Safe Reverse-Dependency Deletion of Dataplex, Pub/Sub & BigQuery Resources
# ==============================================================================
set -euo pipefail

trap 'echo "[ERROR] cleanup.sh failed at line $LINENO" >&2' ERR

# Default Configuration
PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || echo '')}"
REGION="asia-southeast1"
DATASET_ID="sgx_market_data"
TABLE_ID="equity_trades"
TOPIC_ID="sgx-equity-trades-topic"
SCHEMA_ID="sgx-trades-schema"
DLQ_TOPIC_ID="sgx-equity-trades-dlq-topic"
DLQ_SUB_ID="sgx-equity-trades-dlq-sub"
BQ_SUB_ID="sgx-equity-trades-bq-sub"
DATASCAN_ID="sgx-equity-trades-dq"
ASPECT_TYPE_ID="data-contract-spec"
FORCE=false
WITH_CATALOG=false

show_help() {
  cat <<EOF
Usage: ./cleanup.sh [OPTIONS]

Safely deletes all Google Cloud Data Contract resources in reverse dependency order.

Options:
  --project-id=ID         GCP Project ID (default: current gcloud project)
  --region=REGION         GCP Region (default: asia-southeast1)
  --dataset=DATASET       BigQuery dataset ID (default: sgx_market_data)
  --table=TABLE           BigQuery table ID (default: equity_trades)
  --topic=TOPIC           Pub/Sub topic ID (default: sgx-equity-trades-topic)
  --schema=SCHEMA         Pub/Sub schema ID (default: sgx-trades-schema)
  --dlq-topic=DLQ_TOPIC   Dead-letter topic ID (default: sgx-equity-trades-dlq-topic)
  --dlq-sub=DLQ_SUB       Dead-letter pull subscription ID (default: sgx-equity-trades-dlq-sub)
  --sub=SUB               BigQuery direct subscription ID (default: sgx-equity-trades-bq-sub)
  --datascan=SCAN         Dataplex Data Quality Scan ID (default: sgx-equity-trades-dq)
  --aspect-type=ASPECT    Dataplex Aspect Type ID (default: data-contract-spec)
  --with-catalog          Also delete Dataplex Business Glossary, EntryLinks, and Data Product
  --force                 Non-interactive mode; bypass [y/N] confirmation prompt
  -h, --help              Show this help message and exit
EOF
}

# Parse CLI Arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    --project-id=*) PROJECT_ID="${1#*=}" ;;
    --project-id) PROJECT_ID="$2"; shift ;;
    --region=*) REGION="${1#*=}" ;;
    --region) REGION="$2"; shift ;;
    --dataset=*) DATASET_ID="${1#*=}" ;;
    --dataset) DATASET_ID="$2"; shift ;;
    --table=*) TABLE_ID="${1#*=}" ;;
    --table) TABLE_ID="$2"; shift ;;
    --topic=*) TOPIC_ID="${1#*=}" ;;
    --topic) TOPIC_ID="$2"; shift ;;
    --schema=*) SCHEMA_ID="${1#*=}" ;;
    --schema) SCHEMA_ID="$2"; shift ;;
    --dlq-topic=*) DLQ_TOPIC_ID="${1#*=}" ;;
    --dlq-topic) DLQ_TOPIC_ID="$2"; shift ;;
    --dlq-sub=*) DLQ_SUB_ID="${1#*=}" ;;
    --dlq-sub) DLQ_SUB_ID="$2"; shift ;;
    --sub=*) BQ_SUB_ID="${1#*=}" ;;
    --sub) BQ_SUB_ID="$2"; shift ;;
    --datascan=*) DATASCAN_ID="${1#*=}" ;;
    --datascan) DATASCAN_ID="$2"; shift ;;
    --aspect-type=*) ASPECT_TYPE_ID="${1#*=}" ;;
    --aspect-type) ASPECT_TYPE_ID="$2"; shift ;;
    --with-catalog) WITH_CATALOG=true ;;
    --force) FORCE=true ;;
    -h|--help) show_help; exit 0 ;;
    *) echo "[ERROR] Unknown flag: $1" >&2; show_help; exit 1 ;;
  esac
  shift
done

if [[ -z "${PROJECT_ID}" ]]; then
  echo "[ERROR] PROJECT_ID is required. Pass --project-id or set gcloud project." >&2
  exit 1
fi

echo "========================================================================"
echo "   SGX GOOGLE CLOUD DATA CONTRACTS - INFRASTRUCTURE TEARDOWN            "
echo "========================================================================"
echo "Project ID       : ${PROJECT_ID}"
echo "Region           : ${REGION}"
echo "BigQuery Dataset : ${DATASET_ID}"
echo "Pub/Sub Topic    : ${TOPIC_ID}"
echo "DLQ Topic / Sub  : ${DLQ_TOPIC_ID} / ${DLQ_SUB_ID}"
echo "BQ Direct Sub    : ${BQ_SUB_ID}"
echo "Dataplex Scan    : ${DATASCAN_ID}"
echo "Aspect Type      : ${ASPECT_TYPE_ID}"
echo "Force Mode       : ${FORCE}"
echo "========================================================================"

if [[ "${FORCE}" != "true" ]]; then
  echo "WARNING: This will permanently delete all SGX Data Contract resources in project '${PROJECT_ID}':"
  echo "  - Dataplex DataScan: ${DATASCAN_ID}"
  echo "  - Dataplex Aspect Type: ${ASPECT_TYPE_ID}"
  echo "  - Pub/Sub Subscription: ${BQ_SUB_ID}"
  echo "  - Pub/Sub DLQ Subscription: ${DLQ_SUB_ID}"
  echo "  - Pub/Sub Topics: ${TOPIC_ID}, ${DLQ_TOPIC_ID}"
  echo "  - Pub/Sub Schema: ${SCHEMA_ID}"
  echo "  - BigQuery Dataset: ${DATASET_ID} (including all tables and views)"
  read -r -p "Are you sure you want to proceed? [y/N]: " confirm
  if [[ ! "${confirm}" =~ ^[Yy]$ ]]; then
    echo "Cleanup cancelled by user."
    exit 0
  fi
fi

if [[ "${WITH_CATALOG}" == "true" ]]; then
  echo -e "\n>> [Catalog Teardown] Deleting Dataplex Business Glossary, EntryLinks & Data Product..."
  python3 scripts/provision_catalog.py teardown --project-id="${PROJECT_ID}" --location="${REGION}" || true
fi

# Step 1: Dataplex DataScan Teardown
echo -e "\n>> [Step 1/9] Deleting Dataplex DataScan (${DATASCAN_ID})..."
if gcloud dataplex datascans describe "${DATASCAN_ID}" --location="${REGION}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud dataplex datascans delete "${DATASCAN_ID}" \
    --location="${REGION}" \
    --project="${PROJECT_ID}" \
    --quiet 2>/dev/null || true
  echo "   ✓ Dataplex DataScan deleted."
else
  echo "   Dataplex DataScan '${DATASCAN_ID}' not found or already deleted."
fi

# Step 2: Dataplex Aspect Type Teardown
echo -e "\n>> [Step 2/9] Deleting Dataplex Aspect Type (${ASPECT_TYPE_ID})..."
if gcloud dataplex aspect-types describe "${ASPECT_TYPE_ID}" --location="${REGION}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud dataplex aspect-types delete "${ASPECT_TYPE_ID}" \
    --location="${REGION}" \
    --project="${PROJECT_ID}" \
    --quiet 2>/dev/null || true
  echo "   ✓ Dataplex Aspect Type deleted."
else
  echo "   Dataplex Aspect Type '${ASPECT_TYPE_ID}' not found or already deleted."
fi

# Step 3: BigQuery Direct Subscription Teardown
echo -e "\n>> [Step 3/9] Deleting BigQuery Direct Subscription (${BQ_SUB_ID})..."
if gcloud pubsub subscriptions describe "${BQ_SUB_ID}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud pubsub subscriptions delete "${BQ_SUB_ID}" \
    --project="${PROJECT_ID}" \
    --quiet 2>/dev/null || true
  echo "   ✓ BigQuery Direct Subscription deleted."
else
  echo "   Subscription '${BQ_SUB_ID}' not found or already deleted."
fi

# Step 4: DLQ Subscription Teardown
echo -e "\n>> [Step 4/9] Deleting DLQ Subscription (${DLQ_SUB_ID})..."
if gcloud pubsub subscriptions describe "${DLQ_SUB_ID}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud pubsub subscriptions delete "${DLQ_SUB_ID}" \
    --project="${PROJECT_ID}" \
    --quiet 2>/dev/null || true
  echo "   ✓ DLQ Subscription deleted."
else
  echo "   Subscription '${DLQ_SUB_ID}' not found or already deleted."
fi

# Step 5: Pub/Sub Topics Teardown
echo -e "\n>> [Step 5/9] Deleting Pub/Sub Topics (${TOPIC_ID}, ${DLQ_TOPIC_ID})..."
if gcloud pubsub topics describe "${TOPIC_ID}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud pubsub topics delete "${TOPIC_ID}" \
    --project="${PROJECT_ID}" \
    --quiet 2>/dev/null || true
  echo "   ✓ Main topic deleted."
else
  echo "   Main topic '${TOPIC_ID}' not found or already deleted."
fi

if gcloud pubsub topics describe "${DLQ_TOPIC_ID}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud pubsub topics delete "${DLQ_TOPIC_ID}" \
    --project="${PROJECT_ID}" \
    --quiet 2>/dev/null || true
  echo "   ✓ DLQ topic deleted."
else
  echo "   DLQ topic '${DLQ_TOPIC_ID}' not found or already deleted."
fi

# Step 6: Pub/Sub Schema Teardown
echo -e "\n>> [Step 6/9] Deleting Pub/Sub Schema (${SCHEMA_ID})..."
if gcloud pubsub schemas describe "${SCHEMA_ID}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud pubsub schemas delete "${SCHEMA_ID}" \
    --project="${PROJECT_ID}" \
    --quiet 2>/dev/null || true
  echo "   ✓ Schema deleted."
else
  echo "   Schema '${SCHEMA_ID}' not found or already deleted."
fi

# Step 7: BigQuery Reporting View Teardown
echo -e "\n>> [Step 7/9] Deleting BigQuery Reporting View (v_dq_rule_summary)..."
bq rm -f -t "${PROJECT_ID}:${DATASET_ID}.v_dq_rule_summary" 2>/dev/null || true
echo "   ✓ Reporting view deleted (if existed)."

# Step 8: BigQuery Tables Teardown
echo -e "\n>> [Step 8/9] Deleting BigQuery Tables (${TABLE_ID}, dq_export_results)..."
bq rm -f -t "${PROJECT_ID}:${DATASET_ID}.${TABLE_ID}" 2>/dev/null || true
bq rm -f -t "${PROJECT_ID}:${DATASET_ID}.dq_export_results" 2>/dev/null || true
echo "   ✓ Tables deleted (if existed)."

# Step 9: BigQuery Dataset Teardown
echo -e "\n>> [Step 9/9] Deleting BigQuery Dataset (${DATASET_ID})..."
bq rm -r -f -d "${PROJECT_ID}:${DATASET_ID}" 2>/dev/null || true
echo "   ✓ Dataset deleted (if existed)."

echo -e "\n========================================================================"
echo "   [SUCCESS] Cleanup complete. All SGX Data Contract resources removed."
echo "========================================================================"
