#!/usr/bin/env bash
# Create the S3 bucket and Glue database used by the demo.
set -euo pipefail
cd "$(dirname "$0")/.."
source ./config.local.env

echo "== S3 bucket: ${S3_BUCKET} (${AWS_REGION}) =="
if aws s3api head-bucket --bucket "${S3_BUCKET}" 2>/dev/null; then
  echo "  bucket already exists."
else
  if [[ "${AWS_REGION}" == "us-east-1" ]]; then
    aws s3api create-bucket --bucket "${S3_BUCKET}" --region "${AWS_REGION}"
  else
    aws s3api create-bucket --bucket "${S3_BUCKET}" --region "${AWS_REGION}" \
      --create-bucket-configuration LocationConstraint="${AWS_REGION}"
  fi
fi

aws s3api put-public-access-block --bucket "${S3_BUCKET}" \
  --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

echo "== Glue database: ${GLUE_DATABASE} =="
if aws glue get-database --name "${GLUE_DATABASE}" --region "${AWS_REGION}" \
    >/dev/null 2>&1; then
  echo "  database already exists."
else
  aws glue create-database --region "${AWS_REGION}" \
    --database-input "{\"Name\":\"${GLUE_DATABASE}\"}"
fi
echo "Done."
