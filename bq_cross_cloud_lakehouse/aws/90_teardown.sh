#!/usr/bin/env bash
# Preview or execute removal of the AWS demo resources.
set -euo pipefail
cd "$(dirname "$0")/.."
source ./config.local.env

MODE="${1:---dry-run}"
if [[ "${MODE}" != "--dry-run" && "${MODE}" != "--execute" ]]; then
  echo "Usage: $0 [--dry-run|--execute]" >&2
  exit 2
fi

run() {
  printf "  "
  printf "%q " "$@"
  printf "\n"
  if [[ "${MODE}" == "--execute" ]]; then
    "$@"
  fi
}

echo "AWS teardown ${MODE}."
[[ "${MODE}" == "--dry-run" ]] && echo "No resources will be changed."

case "${S3_BUCKET_MODE:-}" in
  dedicated|shared) ;;
  *)
    echo "ERROR: Set S3_BUCKET_MODE to dedicated or shared in config.local.env." >&2
    exit 1
    ;;
esac

echo "== Glue =="
for table in "${FROYO_LOYALTY_TABLE}" "${FROYO_SALES_TABLE}"; do
  if aws glue get-table --database-name "${GLUE_DATABASE}" --name "${table}" \
      --region "${AWS_REGION}" >/dev/null 2>&1; then
    run aws glue delete-table --database-name "${GLUE_DATABASE}" \
      --name "${table}" --region "${AWS_REGION}"
  fi
done
if aws glue get-database --name "${GLUE_DATABASE}" --region "${AWS_REGION}" \
    >/dev/null 2>&1; then
  run aws glue delete-database --name "${GLUE_DATABASE}" --region "${AWS_REGION}"
fi

echo "== S3 =="
if aws s3api head-bucket --bucket "${S3_BUCKET}" --region "${AWS_REGION}" \
    >/dev/null 2>&1; then
  if [[ "${S3_BUCKET_MODE}" == "shared" ]]; then
    run aws s3 rm "s3://${S3_BUCKET}/warehouse/${FROYO_LOYALTY_TABLE}/" \
      --recursive --region "${AWS_REGION}"
    run aws s3 rm "s3://${S3_BUCKET}/warehouse/${FROYO_SALES_TABLE}/" \
      --recursive --region "${AWS_REGION}"
    echo "  Shared bucket and unrelated prefixes will be retained."
  else
    run aws s3 rm "s3://${S3_BUCKET}" --recursive --region "${AWS_REGION}"
    run aws s3api delete-bucket --bucket "${S3_BUCKET}" --region "${AWS_REGION}"
  fi
fi

echo "== IAM =="
if aws iam get-role --role-name "${AWS_ROLE_NAME}" >/dev/null 2>&1; then
  if aws iam get-role-policy --role-name "${AWS_ROLE_NAME}" \
      --policy-name "${AWS_POLICY_NAME}" >/dev/null 2>&1; then
    run aws iam delete-role-policy --role-name "${AWS_ROLE_NAME}" \
      --policy-name "${AWS_POLICY_NAME}"
  fi
  run aws iam delete-role --role-name "${AWS_ROLE_NAME}"
fi
run rm -rf .generated

echo "AWS teardown ${MODE} complete."
