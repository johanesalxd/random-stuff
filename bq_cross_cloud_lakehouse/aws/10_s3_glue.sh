#!/usr/bin/env bash
# Phase 2a: create the S3 bucket (data + Athena results) and the Glue database.
# Idempotent: safe to re-run.
set -euo pipefail
cd "$(dirname "$0")/.."
source ./config.local.env

echo "== S3 bucket: ${S3_BUCKET} (${AWS_REGION}) =="
if aws s3api head-bucket --bucket "${S3_BUCKET}" 2>/dev/null; then
  echo "  bucket already exists."
else
  # us-east-1 must NOT use a LocationConstraint; all other regions must.
  if [[ "${AWS_REGION}" == "us-east-1" ]]; then
    aws s3api create-bucket --bucket "${S3_BUCKET}" --region "${AWS_REGION}"
  else
    aws s3api create-bucket --bucket "${S3_BUCKET}" --region "${AWS_REGION}" \
      --create-bucket-configuration LocationConstraint="${AWS_REGION}"
  fi
  echo "  created."
fi

echo "== Block public access on the bucket (security) =="
aws s3api put-public-access-block --bucket "${S3_BUCKET}" \
  --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

echo "== Glue database: ${GLUE_DATABASE} =="
if aws glue get-database --name "${GLUE_DATABASE}" >/dev/null 2>&1; then
  echo "  database already exists."
else
  aws glue create-database --database-input "{\"Name\":\"${GLUE_DATABASE}\"}"
  echo "  created."
fi
echo "Done."
