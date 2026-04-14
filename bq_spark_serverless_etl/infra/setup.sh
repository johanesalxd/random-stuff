#!/bin/bash
#
# setup.sh -- Provision all GCP resources for the Dataproc Serverless Spark ETL demo.
#
# What this creates:
#   - Enables required GCP APIs
#   - GCS bucket (pipeline artifacts: wheel, main.py, JDBC JAR, configs)
#   - Cloud SQL Postgres instance (demo source database, public IP)
#   - Cloud SQL database + user
#   - Secret Manager secret with the JDBC URL
#   - BigQuery datasets: raw_thelook (ingestion landing) + analytics (transforms)
#   - BigQuery Spark connection (for the stored procedure)
#   - Service account with least-privilege IAM roles
#
# Outputs:
#   infra/.env  -- environment variables consumed by the Makefile and seed script
#
# Prerequisites:
#   gcloud CLI authenticated: gcloud auth login && gcloud auth application-default login
#   bq CLI available (bundled with gcloud)
#
# Usage:
#   GCP_PROJECT=my-project GCP_REGION=us-central1 bash infra/setup.sh

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration (override via env)
# ---------------------------------------------------------------------------

GCP_PROJECT="${GCP_PROJECT:?ERROR: GCP_PROJECT is not set}"
GCP_REGION="${GCP_REGION:?ERROR: GCP_REGION is not set}"
GCS_BUCKET="${GCS_BUCKET:-${GCP_PROJECT}-spark-etl-demo}"
BQ_DATASET="${BQ_DATASET:-pipelines}"
BQ_CONNECTION="${BQ_CONNECTION:-spark-etl-conn}"
SA_NAME="${SA_NAME:-spark-etl-sa}"
SQL_INSTANCE="${SQL_INSTANCE:-thelook-demo}"
SQL_DB="${SQL_DB:-thelook}"
SQL_USER="${SQL_USER:-spark}"
SQL_PASSWORD="${SQL_PASSWORD:-$(python3 -c 'import secrets; print(secrets.token_hex(16))')}"
SECRET_NAME="${SECRET_NAME:-thelook-db-jdbc-url}"

SA_EMAIL="${SA_NAME}@${GCP_PROJECT}.iam.gserviceaccount.com"
ENV_FILE="$(dirname "$0")/.env"

echo "=== Dataproc Serverless Spark ETL Demo Setup ==="
echo "Project : ${GCP_PROJECT}"
echo "Region  : ${GCP_REGION}"
echo "Bucket  : ${GCS_BUCKET}"
echo ""

# ---------------------------------------------------------------------------
# 1. Enable APIs
# ---------------------------------------------------------------------------
echo "[1/9] Enabling GCP APIs..."
gcloud services enable \
  dataproc.googleapis.com \
  bigquery.googleapis.com \
  bigqueryconnection.googleapis.com \
  storage.googleapis.com \
  secretmanager.googleapis.com \
  sqladmin.googleapis.com \
  cloudresourcemanager.googleapis.com \
  --project="${GCP_PROJECT}" \
  --quiet
echo "      APIs enabled."

# ---------------------------------------------------------------------------
# 2. GCS bucket
# ---------------------------------------------------------------------------
echo "[2/9] Creating GCS bucket: gs://${GCS_BUCKET}..."
if gcloud storage buckets describe "gs://${GCS_BUCKET}" \
    --project="${GCP_PROJECT}" &>/dev/null; then
  echo "      Bucket already exists, skipping."
else
  gcloud storage buckets create "gs://${GCS_BUCKET}" \
    --project="${GCP_PROJECT}" \
    --location="${GCP_REGION}" \
    --uniform-bucket-level-access \
    --quiet
  echo "      Bucket created."
fi

# ---------------------------------------------------------------------------
# 3. Service account
# ---------------------------------------------------------------------------
echo "[3/9] Creating service account: ${SA_EMAIL}..."
if gcloud iam service-accounts describe "${SA_EMAIL}" \
    --project="${GCP_PROJECT}" &>/dev/null; then
  echo "      Service account already exists, skipping."
else
  gcloud iam service-accounts create "${SA_NAME}" \
    --display-name="Spark ETL Demo SA" \
    --project="${GCP_PROJECT}" \
    --quiet
  # Allow IAM propagation before binding roles
  sleep 10
fi

echo "      Granting IAM roles..."
for ROLE in \
  roles/dataproc.worker \
  roles/storage.objectAdmin \
  roles/bigquery.dataEditor \
  roles/bigquery.jobUser \
  roles/secretmanager.secretAccessor \
  roles/logging.logWriter; do
  gcloud projects add-iam-policy-binding "${GCP_PROJECT}" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="${ROLE}" \
    --condition=None \
    --quiet > /dev/null
done
echo "      IAM roles granted."

# ---------------------------------------------------------------------------
# 4. BigQuery datasets
# ---------------------------------------------------------------------------
echo "[4/9] Creating BigQuery datasets..."
for DS in raw_thelook analytics "${BQ_DATASET}"; do
  if bq ls --project_id="${GCP_PROJECT}" "${DS}" &>/dev/null; then
    echo "      Dataset ${DS} already exists, skipping."
  else
    bq mk \
      --project_id="${GCP_PROJECT}" \
      --location="${GCP_REGION}" \
      --dataset \
      "${GCP_PROJECT}:${DS}"
    echo "      Dataset ${DS} created."
  fi
done

# ---------------------------------------------------------------------------
# 5. BigQuery Spark connection
# ---------------------------------------------------------------------------
echo "[5/9] Creating BigQuery Spark connection: ${BQ_CONNECTION}..."
if bq show --connection \
    --project_id="${GCP_PROJECT}" \
    --location="${GCP_REGION}" \
    "${BQ_CONNECTION}" &>/dev/null; then
  echo "      Connection already exists, skipping."
else
  bq mk --connection \
    --connection_type=SPARK \
    --project_id="${GCP_PROJECT}" \
    --location="${GCP_REGION}" \
    "${BQ_CONNECTION}"
  echo "      Connection created."
fi

# Grant the connection's service account access to read GCS and secrets.
CONN_SA=$(bq show --connection \
    --project_id="${GCP_PROJECT}" \
    --location="${GCP_REGION}" \
    --format=json \
    "${BQ_CONNECTION}" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['spark']['serviceAccountId'])")

echo "      Connection SA: ${CONN_SA}"
echo "      Granting roles to connection SA..."
for ROLE in \
  roles/storage.objectViewer \
  roles/secretmanager.secretAccessor \
  roles/bigquery.dataEditor \
  roles/bigquery.jobUser; do
  gcloud projects add-iam-policy-binding "${GCP_PROJECT}" \
    --member="serviceAccount:${CONN_SA}" \
    --role="${ROLE}" \
    --condition=None \
    --quiet > /dev/null
done
echo "      Roles granted to connection SA."

# ---------------------------------------------------------------------------
# 6. Cloud SQL Postgres instance
# ---------------------------------------------------------------------------
echo "[6/9] Creating Cloud SQL instance: ${SQL_INSTANCE} (this takes ~5 minutes)..."
if gcloud sql instances describe "${SQL_INSTANCE}" \
    --project="${GCP_PROJECT}" &>/dev/null; then
  echo "      Instance already exists, skipping."
else
  # Use --async so gcloud returns immediately instead of timing out waiting.
  # Pin zone to avoid GCP zone-selection delay.
  gcloud sql instances create "${SQL_INSTANCE}" \
    --project="${GCP_PROJECT}" \
    --region="${GCP_REGION}" \
    --zone="${GCP_REGION}-f" \
    --database-version=POSTGRES_15 \
    --tier=db-f1-micro \
    --storage-size=10GB \
    --storage-type=HDD \
    --availability-type=ZONAL \
    --no-backup \
    --async \
    --quiet
  echo "      Cloud SQL create submitted, waiting for RUNNABLE state..."
  for _i in $(seq 1 40); do
    _STATE=$(gcloud sql instances describe "${SQL_INSTANCE}" \
      --project="${GCP_PROJECT}" \
      --format='value(state)' 2>/dev/null || true)
    echo "      [${_i}/40] state=${_STATE}"
    if [[ "${_STATE}" == "RUNNABLE" ]]; then
      echo "      Instance is RUNNABLE."
      break
    fi
    if [[ "${_i}" -eq 40 ]]; then
      echo "ERROR: Cloud SQL instance did not become RUNNABLE after 10 minutes." >&2
      exit 1
    fi
    sleep 15
  done
fi

echo "[6b/9] Setting root password..."
gcloud sql users set-password postgres \
  --instance="${SQL_INSTANCE}" \
  --project="${GCP_PROJECT}" \
  --password="${SQL_PASSWORD}" \
  --quiet

echo "[6c/9] Creating database: ${SQL_DB}..."
if gcloud sql databases describe "${SQL_DB}" \
    --instance="${SQL_INSTANCE}" \
    --project="${GCP_PROJECT}" &>/dev/null; then
  echo "      Database already exists, skipping."
else
  gcloud sql databases create "${SQL_DB}" \
    --instance="${SQL_INSTANCE}" \
    --project="${GCP_PROJECT}" \
    --quiet
fi

echo "[6d/9] Creating SQL user: ${SQL_USER}..."
if gcloud sql users list \
    --instance="${SQL_INSTANCE}" \
    --project="${GCP_PROJECT}" \
    --format='value(name)' | grep -q "^${SQL_USER}$"; then
  echo "      User already exists, skipping."
else
  gcloud sql users create "${SQL_USER}" \
    --instance="${SQL_INSTANCE}" \
    --project="${GCP_PROJECT}" \
    --password="${SQL_PASSWORD}" \
    --quiet
fi

# Get Cloud SQL public IP
SQL_HOST=$(gcloud sql instances describe "${SQL_INSTANCE}" \
  --project="${GCP_PROJECT}" \
  --format='value(ipAddresses[0].ipAddress)')
echo "      Cloud SQL public IP: ${SQL_HOST}"

# Authorize Dataproc Serverless egress IPs.
# Dataproc Serverless uses Google-managed IPs (0.0.0.0/0 is simplest for demo).
# For production use a VPC + private IP.
echo "[6e/9] Authorizing Cloud SQL public IP access for demo (0.0.0.0/0)..."
gcloud sql instances patch "${SQL_INSTANCE}" \
  --project="${GCP_PROJECT}" \
  --authorized-networks=0.0.0.0/0 \
  --quiet
echo "      Authorized."

# ---------------------------------------------------------------------------
# 7. Secret Manager: JDBC URL
# ---------------------------------------------------------------------------
JDBC_URL="jdbc:postgresql://${SQL_HOST}:5432/${SQL_DB}?user=${SQL_USER}&password=${SQL_PASSWORD}&sslmode=disable"
echo "[7/9] Storing JDBC URL in Secret Manager: ${SECRET_NAME}..."
if gcloud secrets describe "${SECRET_NAME}" \
    --project="${GCP_PROJECT}" &>/dev/null; then
  echo "      Secret exists -- adding new version..."
  echo -n "${JDBC_URL}" | gcloud secrets versions add "${SECRET_NAME}" \
    --data-file=- \
    --project="${GCP_PROJECT}" \
    --quiet
else
  echo -n "${JDBC_URL}" | gcloud secrets create "${SECRET_NAME}" \
    --data-file=- \
    --replication-policy=automatic \
    --project="${GCP_PROJECT}" \
    --quiet
fi
SECRET_RESOURCE="projects/${GCP_PROJECT}/secrets/${SECRET_NAME}/versions/latest"
echo "      Secret resource: ${SECRET_RESOURCE}"

# ---------------------------------------------------------------------------
# 8. Upload demo configs to GCS
# ---------------------------------------------------------------------------
echo "[8/9] Uploading demo configs to GCS..."
REPO_ROOT="$(dirname "$0")/.."
for YAML in "${REPO_ROOT}"/configs/demo/*.yaml; do
  TABLE=$(basename "${YAML}" .yaml)
  sed "s|MY_PROJECT|${GCP_PROJECT}|g" "${YAML}" \
  | gcloud storage cp - \
    "gs://${GCS_BUCKET}/configs/thelook/public/${TABLE}.yaml" \
    --quiet
done
echo "      Configs uploaded."

# ---------------------------------------------------------------------------
# 9. Write .env file
# ---------------------------------------------------------------------------
echo "[9/9] Writing infra/.env..."
cat > "${ENV_FILE}" <<EOF
# Generated by infra/setup.sh -- do not commit
GCP_PROJECT=${GCP_PROJECT}
GCP_REGION=${GCP_REGION}
GCS_BUCKET=${GCS_BUCKET}
BQ_DATASET=${BQ_DATASET}
BQ_CONNECTION=${BQ_CONNECTION}
SERVICE_ACCOUNT=${SA_EMAIL}
SQL_INSTANCE=${SQL_INSTANCE}
SQL_HOST=${SQL_HOST}
SQL_DB=${SQL_DB}
SQL_USER=${SQL_USER}
SQL_PASSWORD=${SQL_PASSWORD}
SECRET_RESOURCE=${SECRET_RESOURCE}
EOF
echo "      Written to ${ENV_FILE}"

echo ""
echo "=== Setup complete ==="
echo ""
echo "Next steps:"
echo "  1. Seed the database:  make seed"
echo "  2. Build and deploy:   make deploy"
echo "  3. Run the pipeline:   make run-demo-pipeline"
echo "  4. Tear down:          make infra-down"
