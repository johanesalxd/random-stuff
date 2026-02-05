#!/bin/bash
set -e

# Cancel running stress test jobs

PROJECT="${GCP_PROJECT:-your-project-id}"
REGION="${GCP_REGION:-asia-southeast1}"
JOB_NAME_PATTERN="bq-stress-test"

FORCE=false
if [[ "$1" == "--force" || "$1" == "-f" ]]; then
  FORCE=true
fi

echo "Scanning for running stress test jobs..."
echo ""

# List running jobs
JOBS=$(gcloud dataflow jobs list \
  --project=$PROJECT \
  --region=$REGION \
  --status=active \
  --format="table(id,name,state,createTime)" \
  --filter="name~$JOB_NAME_PATTERN" 2>/dev/null)

if [ -z "$JOBS" ] || [ "$(echo "$JOBS" | wc -l)" -le 1 ]; then
  echo "No running stress test jobs found."
  exit 0
fi

echo "$JOBS"
echo ""

# Get job IDs only
JOB_IDS=$(gcloud dataflow jobs list \
  --project=$PROJECT \
  --region=$REGION \
  --status=active \
  --format="value(id)" \
  --filter="name~$JOB_NAME_PATTERN" 2>/dev/null)

if [ "$FORCE" = true ]; then
  confirm="y"
else
  read -p "Cancel all listed jobs? (y/N): " confirm
fi

if [[ "$confirm" =~ ^[Yy]$ ]]; then
  for JOB_ID in $JOB_IDS; do
    echo "Cancelling job: $JOB_ID"
    gcloud dataflow jobs cancel $JOB_ID --region=$REGION --project=$PROJECT
  done
  echo ""
  echo "Done. All jobs cancelled."
else
  echo "Aborted."
fi
