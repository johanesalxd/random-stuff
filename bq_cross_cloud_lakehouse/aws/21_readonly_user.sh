#!/usr/bin/env bash
# Create a read-only AWS IAM User (demo_user) with console login access for AWS Glue & Athena (Idempotent)
set -euo pipefail
cd "$(dirname "$0")/.."
source ./config.local.env

USERNAME="${AWS_READONLY_USERNAME:-demo_user}"
POLICY_NAME="${AWS_READONLY_POLICY_NAME:-froyo_readonly_athena_glue_policy}"
RESET_REQUIRED="${AWS_READONLY_RESET_ON_LOGIN:-false}"

mkdir -p .generated

echo "== Check Read-Only IAM User: ${USERNAME} =="
if aws iam get-user --user-name "${USERNAME}" >/dev/null 2>&1; then
  echo "  IAM user ${USERNAME} already exists; skipping user creation."
else
  echo "  Creating IAM user ${USERNAME}..."
  aws iam create-user --user-name "${USERNAME}"
fi

# Generate or read password
PASSWORD="${AWS_READONLY_PASSWORD:-$(openssl rand -base64 16 | tr -dc 'a-zA-Z0-9' | head -c 16)F1!}"

RESET_FLAG="--no-password-reset-required"
if [[ "${RESET_REQUIRED}" == "true" ]]; then
  RESET_FLAG="--password-reset-required"
fi

if aws iam get-login-profile --user-name "${USERNAME}" >/dev/null 2>&1; then
  echo "  Updating login profile password for ${USERNAME}..."
  aws iam update-login-profile --user-name "${USERNAME}" --password "${PASSWORD}" ${RESET_FLAG}
else
  echo "  Creating login profile for ${USERNAME}..."
  aws iam create-login-profile --user-name "${USERNAME}" --password "${PASSWORD}" ${RESET_FLAG}
fi

# Apply inline user policy
sed -e "s|\${AWS_REGION}|${AWS_REGION}|g" \
    -e "s|\${AWS_ACCOUNT_ID}|${AWS_ACCOUNT_ID}|g" \
    -e "s|\${S3_BUCKET}|${S3_BUCKET}|g" \
    -e "s|\${GLUE_DATABASE}|${GLUE_DATABASE}|g" \
    aws/policies/readonly_user_policy.template.json > .generated/readonly_user_policy.local.json

aws iam put-user-policy \
  --user-name "${USERNAME}" \
  --policy-name "${POLICY_NAME}" \
  --policy-document file://.generated/readonly_user_policy.local.json

echo "=========================================================="
echo " AWS Read-Only Console Credentials (${USERNAME})"
echo "=========================================================="
echo " Console Sign-In URL: https://${AWS_ACCOUNT_ID}.signin.aws.amazon.com/console"
echo " Username:           ${USERNAME}"
echo " Password:           ${PASSWORD}"
echo " Password Reset:     ${RESET_REQUIRED}"
echo "=========================================================="
