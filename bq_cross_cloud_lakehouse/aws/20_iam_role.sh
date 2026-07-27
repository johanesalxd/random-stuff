#!/usr/bin/env bash
# Create the AWS IAM role used by BigLake federation.
set -euo pipefail
cd "$(dirname "$0")/.."
source ./config.local.env

mkdir -p .generated

echo "== Create role ${AWS_ROLE_NAME} =="
if aws iam get-role --role-name "${AWS_ROLE_NAME}" >/dev/null 2>&1; then
  echo "  role already exists."
else
  aws iam create-role \
    --role-name "${AWS_ROLE_NAME}" \
    --assume-role-policy-document file://aws/policies/trust_policy.placeholder.json \
    --max-session-duration 43200
fi

sed -e "s|\${AWS_REGION}|${AWS_REGION}|g" \
    -e "s|\${AWS_ACCOUNT_ID}|${AWS_ACCOUNT_ID}|g" \
    -e "s|\${S3_BUCKET}|${S3_BUCKET}|g" \
    aws/policies/permissions_policy.template.json > .generated/permissions_policy.local.json
aws iam put-role-policy \
  --role-name "${AWS_ROLE_NAME}" \
  --policy-name "${AWS_POLICY_NAME}" \
  --policy-document file://.generated/permissions_policy.local.json

echo "Role ARN: arn:aws:iam::${AWS_ACCOUNT_ID}:role/${AWS_ROLE_NAME}"
