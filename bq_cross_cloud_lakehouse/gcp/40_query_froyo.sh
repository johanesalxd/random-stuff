#!/usr/bin/env bash
# Phase 4: the Froyo cross-cloud demo queries, all from BigQuery.
#
#   Q1  Live read of the AWS-federated global_loyalty Iceberg table.
#   Q2  "Find allergens in Midnight Swirl" -> native recipe x supplier knowledge.
#   Q3  "Customer target list" -> allergen knowledge (native, us-east4)
#       CROSS-JOINED with customer loyalty that physically lives in AWS S3/Glue.
#
# Q3 is the payoff: a single BigQuery SQL statement spanning GCP-native tables
# and an AWS-resident Iceberg table, with no data movement and no AWS keys.
set -euo pipefail
cd "$(dirname "$0")/.."
source ./config.local.env

LOYALTY="${GCP_PROJECT}.${FEDERATED_CATALOG}.${GLUE_DATABASE}.${FROYO_LOYALTY_TABLE}"
FQDS="${GCP_PROJECT}.${FROYO_NATIVE_DATASET}"

bq_query() { bq --location="${GCP_REGION}" --project_id="${GCP_PROJECT}" query --use_legacy_sql=false "$1"; }

echo "== Q1: live read of AWS-federated ${LOYALTY} (LIMIT 10) =="
bq_query "SELECT * FROM \`${LOYALTY}\` LIMIT 10"

echo
echo "== Q2: Find allergens in Midnight Swirl (native knowledge) =="
bq_query "SELECT product_name, allergen, ingredient_name, supplier, source_doc
          FROM \`${FQDS}.product_allergens\`
          WHERE product_name = 'Midnight Swirl'"

echo
echo "== Q3: Cross-cloud customer target list for Midnight Swirl =="
echo "   (exclude soy-sensitive customers, since the product contains soy)"
bq_query "
WITH ms_allergens AS (
  SELECT DISTINCT allergen
  FROM \`${FQDS}.product_allergens\`
  WHERE product_name = 'Midnight Swirl'
)
SELECT
  l.customer_id,
  l.region,
  l.loyalty_tier,
  l.avg_monthly_spend
FROM \`${LOYALTY}\` l
WHERE l.favorite_flavor = 'Midnight Swirl'
  AND NOT (l.soy_sensitive_flag AND EXISTS (SELECT 1 FROM ms_allergens WHERE allergen = 'Soy'))
ORDER BY l.avg_monthly_spend DESC"
