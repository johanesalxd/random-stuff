#!/bin/bash
set -e

# BigQuery Storage Write API Stress Test - Job Submission

unset GOOGLE_APPLICATION_CREDENTIALS

# Configuration - Set these environment variables or modify defaults
PROJECT="${GCP_PROJECT:-your-project-id}"
REGION="${GCP_REGION:-asia-southeast1}"
TEMP_BUCKET="${GCP_TEMP_BUCKET:-gs://your-bucket/dataflow/stress-test}"
JOB_NAME="bq-stress-test-$(date +%Y%m%d-%H%M%S)"
BIGQUERY_TABLE="$PROJECT:demo_dataset_asia.stress_test_transactions"

echo "=========================================="
echo "BigQuery Storage Write API Stress Test"
echo "=========================================="
echo "Region: $REGION"
echo "Workers: 5x n2-standard-4"
echo "=========================================="
echo ""

# Drop and recreate table for fresh test
echo "Dropping existing table if exists..."
bq rm -f $BIGQUERY_TABLE 2>/dev/null || true

echo "Creating fresh table..."
bq mk --table \
  --schema=transaction_id:STRING,customer_id:INTEGER,customer_email:STRING,order_timestamp:TIMESTAMP,product_id:STRING,product_name:STRING,product_category:STRING,quantity:INTEGER,unit_price:FLOAT,total_amount:FLOAT,currency:STRING,payment_method:STRING,shipping_address:STRING,order_status:STRING \
  $BIGQUERY_TABLE

echo "Table created successfully."
echo ""

echo "Submitting streaming pipeline..."
uv run python src/bq_stress_test.py \
  --runner=DataflowRunner \
  --project=$PROJECT \
  --region=$REGION \
  --job_name=$JOB_NAME \
  --temp_location=$TEMP_BUCKET \
  --worker_machine_type=n2-standard-4 \
  --num_workers=5 \
  --max_num_workers=5 \
  --autoscaling_algorithm=NONE \
  --streaming

echo ""
echo "Job submitted. Monitor at:"
echo "https://console.cloud.google.com/dataflow/jobs/$REGION?project=$PROJECT"
echo ""
echo "To cancel: ./cancel.sh"
