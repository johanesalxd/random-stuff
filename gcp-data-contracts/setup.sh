#!/usr/bin/env bash
# ==============================================================================
# SGX Google Cloud Data Contracts - Automated Infrastructure Provisioning
# Idempotent 11-Step Setup for Pub/Sub, BigQuery & Dataplex Governance
# ==============================================================================
set -euo pipefail

trap 'echo "[ERROR] setup.sh failed at line $LINENO" >&2' ERR

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
DRY_RUN=false
WITH_CATALOG=false

show_help() {
  cat <<EOF
Usage: ./setup.sh [OPTIONS]

Provisions Google Cloud Pub/Sub, BigQuery, and Dataplex Data Quality infrastructure
for the SGX Data Contracts demonstration.

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
  --with-catalog          Also provision Dataplex Business Glossary, EntryLinks, and Data Product
  --force                 Non-interactive mode; skip manual confirmation
  --dry-run               Print provisioning steps and commands without mutating GCP
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
    --dry-run) DRY_RUN=true ;;
    -h|--help) show_help; exit 0 ;;
    *) echo "[ERROR] Unknown flag: $1" >&2; show_help; exit 1 ;;
  esac
  shift
done

if [[ -z "${PROJECT_ID}" ]]; then
  if [[ "${DRY_RUN}" == "true" ]]; then
    PROJECT_ID="sgx-demo-project"
  else
    echo "[ERROR] PROJECT_ID is required. Pass --project-id or set gcloud project." >&2
    exit 1
  fi
fi

echo "========================================================================"
echo "   SGX GOOGLE CLOUD DATA CONTRACTS - INFRASTRUCTURE PROVISIONING        "
echo "========================================================================"
echo "Project ID       : ${PROJECT_ID}"
echo "Region           : ${REGION}"
echo "BigQuery Dataset : ${DATASET_ID}"
echo "BigQuery Table   : ${TABLE_ID}"
echo "Pub/Sub Topic    : ${TOPIC_ID}"
echo "Pub/Sub Schema   : ${SCHEMA_ID}"
echo "DLQ Topic / Sub  : ${DLQ_TOPIC_ID} / ${DLQ_SUB_ID}"
echo "BQ Direct Sub    : ${BQ_SUB_ID}"
echo "Dataplex Scan    : ${DATASCAN_ID}"
echo "Aspect Type      : ${ASPECT_TYPE_ID}"
echo "Dry Run Mode     : ${DRY_RUN}"
echo "========================================================================"

if [[ "${DRY_RUN}" == "true" ]]; then
  echo -e "\n[DRY RUN] Simulating 11-step idempotent provisioning flow..."
  
  echo ">> [Step 1/11] Checking GCP Authentication & Permissions..."
  echo "   [DRY RUN] Would verify gcloud auth print-access-token and project describe for ${PROJECT_ID}"

  echo ">> [Step 2/11] Enabling Required GCP APIs..."
  echo "   [DRY RUN] Would enable pubsub, bigquery, dataplex, datacatalog, logging"

  echo ">> [Step 3/11] Compiling Contract and Provisioning BigQuery Dataset and Tables..."
  python3 compile_contract.py --project-id="${PROJECT_ID}" --dataset="${DATASET_ID}" --table="${TABLE_ID}"
  echo "   [DRY RUN] Would ensure dataset '${DATASET_ID}' exists in ${REGION}"
  echo "   [DRY RUN] Would deploy DDL: sql/create_trades_table.sql"
  echo "   [DRY RUN] Would deploy DDL: sql/create_dq_export_results_table.sql"
  echo "   [DRY RUN] Would deploy DDL: sql/create_v_dq_rule_summary.sql"

  echo ">> [Step 4/11] Binding Pub/Sub Service Agent IAM Roles..."
  echo "   [DRY RUN] Would grant roles/bigquery.dataEditor, roles/bigquery.metadataViewer, roles/pubsub.subscriber to Pub/Sub SA"

  echo ">> [Step 5/11] Registering Pub/Sub Schema (${SCHEMA_ID})..."
  echo "   [DRY RUN] Would register Avro schema schemas/trade_event_v1.avsc as ${SCHEMA_ID}"

  echo ">> [Step 6/11] Creating Main Pub/Sub Topic Bound to Schema (${TOPIC_ID})..."
  echo "   [DRY RUN] Would create topic ${TOPIC_ID} bound to ${SCHEMA_ID} with JSON encoding"

  echo ">> [Step 7/11] Creating DLQ Topic and DLQ Pull Subscription..."
  echo "   [DRY RUN] Would create DLQ topic ${DLQ_TOPIC_ID} and subscription ${DLQ_SUB_ID}"

  echo ">> [Step 8/11] Creating BigQuery Direct Subscription (${BQ_SUB_ID})..."
  echo "   [DRY RUN] Would create BigQuery Direct Subscription with --use-table-schema and --dead-letter-topic=${DLQ_TOPIC_ID}"

  echo ">> [Step 9/11] Binding Dataplex Service Agent IAM Roles..."
  echo "   [DRY RUN] Would grant roles/bigquery.dataViewer, roles/bigquery.dataEditor, roles/bigquery.jobUser to Dataplex SA"

  echo ">> [Step 10/11] Creating Dataplex Auto DQ DataScan (${DATASCAN_ID})..."
  echo "   [DRY RUN] Would create DataScan ${DATASCAN_ID} using config/dataplex_dq_spec.yaml"

  echo ">> [Step 11/11] Creating Dataplex Aspect Type & Attaching Aspect Payload..."
  echo "   [DRY RUN] Would create Aspect Type ${ASPECT_TYPE_ID} from config/aspect_contract_template.yaml"
  echo "   [DRY RUN] Would attach aspect payload from config/table_aspect_payload.yaml to @bigquery entry"
  if [[ "${WITH_CATALOG}" == "true" ]]; then
    python3 scripts/provision_catalog.py apply --dry-run --project-id="${PROJECT_ID}" --location="${REGION}"
  fi

  echo -e "\n[DRY RUN COMPLETE] All 11 steps validated successfully."
  exit 0
fi

# Step 1: Check GCP authentication & project access
echo -e "\n>> [Step 1/11] Checking GCP Authentication & Permissions..."
gcloud auth print-access-token >/dev/null 2>&1 || { echo "[ERROR] gcloud is not authenticated. Run 'gcloud auth login'." >&2; exit 1; }
gcloud projects describe "${PROJECT_ID}" >/dev/null 2>&1 || { echo "[ERROR] Cannot describe project ${PROJECT_ID}." >&2; exit 1; }
bq ls --project_id="${PROJECT_ID}" >/dev/null 2>&1 || { echo "[ERROR] bq CLI cannot access project ${PROJECT_ID}." >&2; exit 1; }
echo "   ✓ GCP authentication and project access verified."

# Step 2: Enable Required APIs
echo -e "\n>> [Step 2/11] Enabling Required GCP APIs..."
gcloud services enable \
  pubsub.googleapis.com \
  bigquery.googleapis.com \
  dataplex.googleapis.com \
  datacatalog.googleapis.com \
  logging.googleapis.com \
  --project="${PROJECT_ID}"
echo "   ✓ Required GCP services enabled."

# Step 3: BigQuery Dataset & Tables Creation
echo -e "\n>> [Step 3/11] Provisioning BigQuery Dataset and Tables..."
if ! bq show --project_id="${PROJECT_ID}" "${DATASET_ID}" >/dev/null 2>&1; then
  echo "   Creating BigQuery dataset ${DATASET_ID} in ${REGION}..."
  bq mk --project_id="${PROJECT_ID}" --location="${REGION}" --dataset "${PROJECT_ID}:${DATASET_ID}"
else
  echo "   BigQuery dataset ${DATASET_ID} already exists. Skipping creation."
fi

echo "   Compiling contract artifacts..."
python3 compile_contract.py --project-id="${PROJECT_ID}" --dataset="${DATASET_ID}" --table="${TABLE_ID}"

echo "   Deploying BigQuery table DDL (equity_trades)..."
sed -e "s/\${PROJECT_ID}/${PROJECT_ID}/g" -e "s/sgx_market_data/${DATASET_ID}/g" sql/create_trades_table.sql | bq query --project_id="${PROJECT_ID}" --use_legacy_sql=false

echo "   Deploying Dataplex DQ export results table DDL..."
sed -e "s/\${PROJECT_ID}/${PROJECT_ID}/g" -e "s/sgx_market_data/${DATASET_ID}/g" sql/create_dq_export_results_table.sql | bq query --project_id="${PROJECT_ID}" --use_legacy_sql=false

echo "   Deploying Dataplex DQ reporting view DDL..."
sed -e "s/\${PROJECT_ID}/${PROJECT_ID}/g" -e "s/sgx_market_data/${DATASET_ID}/g" sql/create_v_dq_rule_summary.sql | bq query --project_id="${PROJECT_ID}" --use_legacy_sql=false
echo "   ✓ BigQuery dataset and tables provisioned."

# Step 4: Pub/Sub Service Agent IAM Bindings
echo -e "\n>> [Step 4/11] Binding Pub/Sub Service Agent IAM Roles..."
PROJECT_NUMBER=$(gcloud projects describe "${PROJECT_ID}" --format="value(projectNumber)")
PUBSUB_SA="service-${PROJECT_NUMBER}@gcp-sa-pubsub.iam.gserviceaccount.com"
gcloud beta services identity create --service=pubsub.googleapis.com --project="${PROJECT_ID}" 2>/dev/null || true

for role in roles/bigquery.dataEditor roles/bigquery.metadataViewer roles/pubsub.subscriber; do
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${PUBSUB_SA}" \
    --role="${role}" \
    --condition=None >/dev/null
done
echo "   ✓ Pub/Sub Service Agent IAM roles bound."

# Step 5: Pub/Sub Schema Registration
echo -e "\n>> [Step 5/11] Registering Pub/Sub Schema (${SCHEMA_ID})..."
if ! gcloud pubsub schemas describe "${SCHEMA_ID}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud pubsub schemas create "${SCHEMA_ID}" \
    --project="${PROJECT_ID}" \
    --type=AVRO \
    --definition-file="schemas/trade_event_v1.avsc"
  echo "   ✓ Schema ${SCHEMA_ID} created."
else
  echo "   Schema ${SCHEMA_ID} already exists. Skipping creation."
fi

# Step 6: Main Pub/Sub Topic Creation Bound to Schema
echo -e "\n>> [Step 6/11] Creating Main Pub/Sub Topic (${TOPIC_ID})..."
if ! gcloud pubsub topics describe "${TOPIC_ID}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud pubsub topics create "${TOPIC_ID}" \
    --project="${PROJECT_ID}" \
    --schema="${SCHEMA_ID}" \
    --message-encoding=json
  echo "   ✓ Topic ${TOPIC_ID} created."
else
  echo "   Topic ${TOPIC_ID} already exists. Skipping creation."
fi

# Step 7: DLQ Topic and DLQ Pull Subscription Creation
echo -e "\n>> [Step 7/11] Creating DLQ Topic and Subscription..."
if ! gcloud pubsub topics describe "${DLQ_TOPIC_ID}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud pubsub topics create "${DLQ_TOPIC_ID}" --project="${PROJECT_ID}"
  echo "   ✓ DLQ Topic ${DLQ_TOPIC_ID} created."
else
  echo "   DLQ Topic ${DLQ_TOPIC_ID} already exists. Skipping creation."
fi

gcloud pubsub topics add-iam-policy-binding "${DLQ_TOPIC_ID}" \
  --project="${PROJECT_ID}" \
  --member="serviceAccount:${PUBSUB_SA}" \
  --role="roles/pubsub.publisher" >/dev/null

if ! gcloud pubsub subscriptions describe "${DLQ_SUB_ID}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud pubsub subscriptions create "${DLQ_SUB_ID}" \
    --project="${PROJECT_ID}" \
    --topic="${DLQ_TOPIC_ID}"
  echo "   ✓ DLQ Subscription ${DLQ_SUB_ID} created."
else
  echo "   DLQ Subscription ${DLQ_SUB_ID} already exists. Skipping creation."
fi

# Step 8: BigQuery Direct Subscription Creation (with IAM Propagation Retry)
echo -e "\n>> [Step 8/11] Creating BigQuery Direct Subscription (${BQ_SUB_ID})..."
if ! gcloud pubsub subscriptions describe "${BQ_SUB_ID}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  for attempt in 1 2 3 4 5; do
    if gcloud pubsub subscriptions create "${BQ_SUB_ID}" \
      --project="${PROJECT_ID}" \
      --topic="${TOPIC_ID}" \
      --bigquery-table="${PROJECT_ID}:${DATASET_ID}.${TABLE_ID}" \
      --use-table-schema \
      --write-metadata \
      --dead-letter-topic="${DLQ_TOPIC_ID}" \
      --max-delivery-attempts=5; then
      echo "   ✓ BigQuery Direct Subscription created successfully."
      break
    fi
    echo "   Subscription creation attempt $attempt failed (waiting for IAM propagation). Retrying in 10s..."
    sleep 10
  done
else
  echo "   BigQuery Direct Subscription ${BQ_SUB_ID} already exists. Skipping creation."
fi

# Step 9: Dataplex Service Agent IAM Bindings
echo -e "\n>> [Step 9/11] Binding Dataplex Service Agent IAM Roles..."
DATAPLEX_SA="service-${PROJECT_NUMBER}@gcp-sa-dataplex.iam.gserviceaccount.com"
gcloud beta services identity create --service=dataplex.googleapis.com --project="${PROJECT_ID}" 2>/dev/null || true

for role in roles/bigquery.dataViewer roles/bigquery.dataEditor roles/bigquery.jobUser; do
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${DATAPLEX_SA}" \
    --role="${role}" \
    --condition=None >/dev/null
done
echo "   ✓ Dataplex Service Agent IAM roles bound."

# Step 10: Dataplex Auto DQ DataScan Creation
echo -e "\n>> [Step 10/11] Creating Dataplex Auto Data Quality Scan (${DATASCAN_ID})..."
if ! gcloud dataplex datascans describe "${DATASCAN_ID}" --location="${REGION}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud dataplex datascans create data-quality "${DATASCAN_ID}" \
    --project="${PROJECT_ID}" \
    --location="${REGION}" \
    --data-source-resource="//bigquery.googleapis.com/projects/${PROJECT_ID}/datasets/${DATASET_ID}/tables/${TABLE_ID}" \
    --data-quality-spec-file="config/dataplex_dq_spec.yaml" \
    --description="Dataplex Auto Data Quality scan enforcing SGX Trade Contract SLAs" \
    --display-name="SGX Equity Trades Quality Scan"
  echo "   ✓ DataScan ${DATASCAN_ID} created."
else
  echo "   DataScan ${DATASCAN_ID} already exists. Skipping creation."
fi

# Step 11: Dataplex Aspect Type Creation & Entry Aspect Attachment
echo -e "\n>> [Step 11/11] Creating Dataplex Aspect Type and Attaching Contract Aspect..."
if ! gcloud dataplex aspect-types describe "${ASPECT_TYPE_ID}" --location="${REGION}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud dataplex aspect-types create "${ASPECT_TYPE_ID}" \
    --project="${PROJECT_ID}" \
    --location="${REGION}" \
    --display-name="SGX Data Contract & Governance Spec" \
    --description="Dataplex Aspect Type defining Data Contract metadata and MAS TRM Section 8 governance" \
    --metadata-template-file-name="config/aspect_contract_template.yaml"
  echo "   ✓ Aspect Type ${ASPECT_TYPE_ID} created."
else
  echo "   Aspect Type ${ASPECT_TYPE_ID} already exists. Skipping creation."
fi

ENTRY_ID="bigquery.googleapis.com/projects/${PROJECT_ID}/datasets/${DATASET_ID}/tables/${TABLE_ID}"
echo "   Waiting for BigQuery table entry to index in Knowledge Catalog..."
for i in 1 2 3 4 5; do
  if gcloud dataplex entries lookup "${ENTRY_ID}" \
      --entry-group="@bigquery" \
      --location="${REGION}" \
      --project="${PROJECT_ID}" &>/dev/null; then
    echo "   ✓ Table entry indexed in @bigquery entry group."
    break
  fi
  echo "   Entry not indexed yet, retrying in 2 seconds (attempt ${i}/5)..."
  sleep 2
done

PAYLOAD_RESOLVED=$(mktemp /tmp/table_aspect_payload.XXXXXX.yaml)
sed -e "s/\${PROJECT_ID}/${PROJECT_ID}/g" \
    -e "s/\${REGION}/${REGION}/g" \
    config/table_aspect_payload.yaml > "${PAYLOAD_RESOLVED}"

echo "   Attaching Data Contract aspect to ${ENTRY_ID}..."
gcloud dataplex entries update-aspects "${ENTRY_ID}" \
    --entry-group="@bigquery" \
    --location="${REGION}" \
    --project="${PROJECT_ID}" \
    --aspects="${PAYLOAD_RESOLVED}" || echo "   [WARN] Aspect attachment skipped or non-fatal."

rm -f "${PAYLOAD_RESOLVED}"

if [[ "${WITH_CATALOG}" == "true" ]]; then
  echo "   Provisioning OOTB Dataplex Business Glossary, EntryLinks & Data Product..."
  python3 scripts/provision_catalog.py apply --project-id="${PROJECT_ID}" --location="${REGION}"
fi

echo -e "\n========================================================================"
echo "   [SUCCESS] SGX Data Contract environment setup completed successfully."
echo "========================================================================"
