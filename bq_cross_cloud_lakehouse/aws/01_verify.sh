#!/usr/bin/env bash
# Verify AWS CLI is configured and pointing at the expected account/region.
# Credentials come from ~/.aws (via `aws configure`), never from this repo.
set -euo pipefail
cd "$(dirname "$0")/.."
source ./config.local.env

echo "Expected account: ${AWS_ACCOUNT_ID} | region: ${AWS_REGION}"
echo "--- aws sts get-caller-identity ---"
aws sts get-caller-identity

ACTUAL_ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
if [[ "${ACTUAL_ACCOUNT}" != "${AWS_ACCOUNT_ID}" ]]; then
  echo "ERROR: CLI account (${ACTUAL_ACCOUNT}) != config AWS_ACCOUNT_ID (${AWS_ACCOUNT_ID})" >&2
  exit 1
fi
echo "OK: CLI is authenticated to the expected account."
