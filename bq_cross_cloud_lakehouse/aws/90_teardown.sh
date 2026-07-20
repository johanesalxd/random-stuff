#!/usr/bin/env bash
# Phase 5 (AWS): remove all demo resources to stop any spend.
# Run AFTER the demo. Idempotent; ignores "not found" errors.
set -uo pipefail
cd "$(dirname "$0")/.."
source ./config.local.env

echo "== Drop Glue table + database =="
aws glue delete-table --database-name "${GLUE_DATABASE}" --name "${ICEBERG_TABLE}" 2>/dev/null || true
aws glue delete-database --name "${GLUE_DATABASE}" 2>/dev/null || true

echo "== Empty + delete S3 bucket ${S3_BUCKET} =="
aws s3 rm "s3://${S3_BUCKET}" --recursive 2>/dev/null || true
aws s3api delete-bucket --bucket "${S3_BUCKET}" --region "${AWS_REGION}" 2>/dev/null || true

echo "== Delete IAM role policy + role =="
aws iam delete-role-policy --role-name "${AWS_ROLE_NAME}" --policy-name "${AWS_POLICY_NAME}" 2>/dev/null || true
aws iam delete-role --role-name "${AWS_ROLE_NAME}" 2>/dev/null || true

echo
echo "OPTIONAL (removes the demo CLI identity entirely = rotates the leaked key):"
echo "  # list + delete access keys, then the user:"
echo "  aws iam list-access-keys --user-name ${AWS_IAM_USER}"
echo "  aws iam delete-access-key --user-name ${AWS_IAM_USER} --access-key-id <ID>"
echo "  aws iam detach-user-policy --user-name ${AWS_IAM_USER} --policy-arn arn:aws:iam::aws:policy/AdministratorAccess"
echo "  aws iam delete-user --user-name ${AWS_IAM_USER}"
echo
echo "AWS teardown complete (core resources removed)."
