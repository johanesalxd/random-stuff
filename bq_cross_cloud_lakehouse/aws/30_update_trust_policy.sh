#!/usr/bin/env bash
# Phase 3b: finalize the IAM role trust policy with the BigLake service-account ID
# that GCP generated when the federated catalog was created.
#
# Usage:  ./aws/30_update_trust_policy.sh <BIGLAKE_SA_ID>
# (gcp/10_create_federated_catalog.sh prints this value.)
set -euo pipefail
cd "$(dirname "$0")/.."
source ./config.local.env

BIGLAKE_SA_ID="${1:-}"
if [[ -z "${BIGLAKE_SA_ID}" ]]; then
  echo "ERROR: pass the BigLake service-account ID as arg 1." >&2
  echo "  Get it: gcloud alpha biglake iceberg catalogs describe ${FEDERATED_CATALOG} \\" >&2
  echo "            --project=${GCP_PROJECT} --format='value(biglake-service-account-id)'" >&2
  exit 1
fi

# This rendered file contains the SA ID -> git-ignored on purpose.
cat > .generated/trust_policy_comprehensive.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "Federated": "accounts.google.com" },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "accounts.google.com:aud": [ "${BIGLAKE_SA_ID}" ],
          "accounts.google.com:sub": [ "${BIGLAKE_SA_ID}" ]
        }
      }
    }
  ]
}
EOF

echo "== Applying finalized trust policy to ${AWS_ROLE_NAME} =="
aws iam update-assume-role-policy \
  --role-name "${AWS_ROLE_NAME}" \
  --policy-document file://.generated/trust_policy_comprehensive.json
echo "Done. Note: AWS IAM changes can take a few minutes to propagate."
