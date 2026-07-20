#!/usr/bin/env bash
# Phase 2c: create the AWS IAM role BigLake will assume (via OIDC web identity),
# starting with a PLACEHOLDER trust policy, plus a scoped Glue/S3 read policy.
# The trust policy is finalized later by 30_update_trust_policy.sh.
set -euo pipefail
cd "$(dirname "$0")/.."
source ./config.local.env

mkdir -p .generated

echo "== Create role ${AWS_ROLE_NAME} (12h max session) =="
if aws iam get-role --role-name "${AWS_ROLE_NAME}" >/dev/null 2>&1; then
  echo "  role already exists (skipping create)."
else
  aws iam create-role \
    --role-name "${AWS_ROLE_NAME}" \
    --assume-role-policy-document file://aws/policies/trust_policy.placeholder.json \
    --max-session-duration 43200
  echo "  created."
fi

echo "== Render + attach scoped permissions policy ${AWS_POLICY_NAME} =="
# Render template with sed (no envsubst dependency) into the git-ignored .generated dir.
sed -e "s|\${AWS_REGION}|${AWS_REGION}|g" \
    -e "s|\${AWS_ACCOUNT_ID}|${AWS_ACCOUNT_ID}|g" \
    -e "s|\${S3_BUCKET}|${S3_BUCKET}|g" \
    aws/policies/permissions_policy.template.json > .generated/permissions_policy.local.json
aws iam put-role-policy \
  --role-name "${AWS_ROLE_NAME}" \
  --policy-name "${AWS_POLICY_NAME}" \
  --policy-document file://.generated/permissions_policy.local.json
echo "  attached."

echo "Role ARN: arn:aws:iam::${AWS_ACCOUNT_ID}:role/${AWS_ROLE_NAME}"
