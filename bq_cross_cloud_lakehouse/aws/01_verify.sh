#!/usr/bin/env bash
# Verify AWS CLI authentication and the Athena engine used by the demo.
set -euo pipefail
cd "$(dirname "$0")/.."
source ./config.local.env

echo "Expected account: ${AWS_ACCOUNT_ID} | region: ${AWS_REGION}"
aws sts get-caller-identity

ACTUAL_ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
if [[ "${ACTUAL_ACCOUNT}" != "${AWS_ACCOUNT_ID}" ]]; then
  echo "ERROR: CLI account (${ACTUAL_ACCOUNT}) != config AWS_ACCOUNT_ID (${AWS_ACCOUNT_ID})" >&2
  exit 1
fi

ATHENA_WORKGROUP="${ATHENA_WORKGROUP:-primary}"
ENGINE_VERSION="$(aws athena get-work-group --work-group "${ATHENA_WORKGROUP}" \
  --region "${AWS_REGION}" \
  --query 'WorkGroup.Configuration.EngineVersion.EffectiveEngineVersion' \
  --output text)"
if [[ "${ENGINE_VERSION}" != "Athena engine version 3" ]]; then
  echo "ERROR: Athena workgroup ${ATHENA_WORKGROUP} must use engine version 3." >&2
  exit 1
fi

echo "OK: AWS account and Athena engine are ready."
