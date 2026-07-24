#!/usr/bin/env bash
# Phase 4: seed the native BigQuery "knowledge" tables in us-east4.
#
# These represent the Knowledge-Catalog-extracted structured data from the
# recipe/supplier PDFs (the deterministic fallback for the demo). The optional
# real Dataplex extraction (gcp/06_knowledge_catalog.sh) publishes equivalent
# tables from the actual PDFs.
#
# They MUST live in GCP_REGION (us-east4) so they can JOIN the AWS-federated
# Iceberg tables (global_loyalty / sales_history) in a single BigQuery query.
set -euo pipefail
cd "$(dirname "$0")/.."
source ./config.local.env

DS="${GCP_PROJECT}:${FROYO_NATIVE_DATASET}"
FQDS="${GCP_PROJECT}.${FROYO_NATIVE_DATASET}"

echo "== Create native dataset ${DS} in ${GCP_REGION} =="
if bq --project_id="${GCP_PROJECT}" show --dataset "${DS}" >/dev/null 2>&1; then
  echo "  dataset already exists."
else
  bq --location="${GCP_REGION}" mk --dataset \
    --description="Froyo Knowledge Catalog (extracted allergen/recipe/product knowledge)" \
    "${DS}"
fi

bq_query() { bq --location="${GCP_REGION}" --project_id="${GCP_PROJECT}" query --use_legacy_sql=false "$1"; }

# NOTE: ingredient/product/allergen values mirror the REAL codelab PDFs vendored
# under assets/pdfs/ (recipes/midnight_swirl.pdf, suppliers/midnight_base_204_manual.pdf),
# so this deterministic seed and the optional Knowledge-Catalog extraction agree.
# products is context for the story / VS Code agent path; the demo queries
# (gcp/40, gcp/50) use recipes, ingredient_allergens and product_allergens.
echo "== Seed products (real codelab flavor names) =="
bq_query "CREATE OR REPLACE TABLE \`${FQDS}.products\` AS
SELECT * FROM UNNEST([
  STRUCT(1 AS product_id, 'Midnight Swirl' AS product_name, 'Frozen Beverage Base' AS category, DATE '2026-01-15' AS launch_date, 'Active' AS status),
  STRUCT(2, 'Midnight Papaya Halo', 'Fruit',   DATE '2025-11-03', 'Active'),
  STRUCT(3, 'Arctic Basil Flow',    'Herbal',  DATE '2025-08-20', 'Active'),
  STRUCT(4, 'Aura Berry Impact',    'Fruit',   DATE '2025-06-01', 'Active')
]);"

echo "== Seed recipes (Midnight Swirl ingredient list, verbatim from midnight_swirl.pdf) =="
bq_query "CREATE OR REPLACE TABLE \`${FQDS}.recipes\` AS
SELECT * FROM UNNEST([
  STRUCT(1 AS product_id, 'Midnight Swirl' AS product_name, 201 AS ingredient_id, 'Midnight Base 204' AS ingredient_name, 120.0 AS quantity_g),
  STRUCT(1, 'Midnight Swirl', 202, 'Aura Acai Gum',            20.0),
  STRUCT(1, 'Midnight Swirl', 203, 'Pulsar Guar Oil',          15.0),
  STRUCT(1, 'Midnight Swirl', 204, 'Galactic Acacia Lecithin',  8.0),
  STRUCT(1, 'Midnight Swirl', 205, 'Martian Ginger Gum',       10.0),
  STRUCT(1, 'Midnight Swirl', 206, 'Cyber Acai Gum',           12.0),
  STRUCT(1, 'Midnight Swirl', 207, 'Lunar Lemon Protein',      18.0),
  STRUCT(1, 'Midnight Swirl', 208, 'Vortex Sunflower Protein', 22.0),
  STRUCT(1, 'Midnight Swirl', 209, 'Neuro-Matrix 994',          5.0),
  STRUCT(1, 'Midnight Swirl', 210, 'Cyber Guava Powder',       14.0),
  STRUCT(1, 'Midnight Swirl', 211, 'Neuro-Matrix 914',          5.0)
]);"

echo "== Seed ingredient_allergens (from supplier datasheets; only allergen-bearing rows) =="
# midnight_base_204_manual.pdf 'ALLERGEN COMPLIANCE PROFILE' declares Soy = Yes.
bq_query "CREATE OR REPLACE TABLE \`${FQDS}.ingredient_allergens\` AS
SELECT * FROM UNNEST([
  STRUCT(201 AS ingredient_id, 'Midnight Base 204' AS ingredient_name, 'Soy' AS allergen, 'Prestige Molecular Additives' AS supplier, 'midnight_base_204_manual.pdf' AS source_doc)
]);"

echo "== Create convenience view product_allergens =="
bq_query "CREATE OR REPLACE VIEW \`${FQDS}.product_allergens\` AS
SELECT DISTINCT r.product_id, r.product_name, a.allergen, a.ingredient_name, a.supplier, a.source_doc
FROM \`${FQDS}.recipes\` r
JOIN \`${FQDS}.ingredient_allergens\` a USING (ingredient_id);"

echo
echo "Done. Native knowledge tables seeded in ${FQDS}:"
echo "  products, recipes, ingredient_allergens, product_allergens (view)"
