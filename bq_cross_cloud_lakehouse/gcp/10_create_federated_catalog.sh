#!/usr/bin/env bash
# Phase 3a: create the BigLake Iceberg federated catalog pointing at AWS Glue.
# Created WITHOUT a refresh schedule (defaults to 0s) so background refresh does
# not fail while the AWS trust relationship is still propagating.
#
# Prints the biglake-service-account-id you must feed to aws/30_update_trust_policy.sh
set -euo pipefail
cd "$(dirname "$0")/.."
source ./config.local.env

ROLE_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:role/${AWS_ROLE_NAME}"

echo "== Create federated catalog ${FEDERATED_CATALOG} in ${GCP_REGION} ==" >&2
if gcloud alpha biglake iceberg catalogs describe "${FEDERATED_CATALOG}" \
     --project="${GCP_PROJECT}" >/dev/null 2>&1; then
  echo "  catalog already exists (skipping create)." >&2
else
  gcloud alpha biglake iceberg catalogs create "${FEDERATED_CATALOG}" \
    --project="${GCP_PROJECT}" \
    --primary-location="${GCP_REGION}" \
    --catalog-type="federated" \
    --federated-catalog-type="glue" \
    --glue-warehouse="${AWS_ACCOUNT_ID}" \
    --glue-aws-region="${AWS_REGION}" \
    --glue-aws-role-arn="${ROLE_ARN}" >&2
fi

BIGLAKE_SA_ID="$(gcloud alpha biglake iceberg catalogs describe "${FEDERATED_CATALOG}" \
  --project="${GCP_PROJECT}" --format='value(biglake-service-account-id)')"
if [[ ! "${BIGLAKE_SA_ID}" =~ ^[0-9]{10,30}$ ]]; then
  echo "ERROR: Catalog returned an invalid BigLake service-account ID." >&2
  exit 1
fi
echo "${BIGLAKE_SA_ID}"
echo "Next: ./aws/30_update_trust_policy.sh ${BIGLAKE_SA_ID}" >&2
