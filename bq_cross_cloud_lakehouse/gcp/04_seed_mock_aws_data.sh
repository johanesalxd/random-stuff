#!/usr/bin/env bash
# Seed mock AWS tables natively in BigQuery for No-AWS testing.
set -euo pipefail
cd "$(dirname "$0")/.."
source ./config.local.env

FQDS="${GCP_PROJECT}.${FROYO_NATIVE_DATASET}"

echo "== Create and seed mock global_loyalty in ${FQDS} =="
bq --location="${GCP_REGION}" --project_id="${GCP_PROJECT}" query --use_legacy_sql=false "
CREATE OR REPLACE TABLE \`${FQDS}.${FROYO_LOYALTY_TABLE}\` (
  customer_id       INT64,
  region            STRING,
  loyalty_tier      STRING,
  favorite_flavor   STRING,
  avg_monthly_spend FLOAT64,
  soy_sensitive_flag BOOL,
  last_order_date   DATE
);

INSERT INTO \`${FQDS}.${FROYO_LOYALTY_TABLE}\` VALUES
(1001, 'APAC', 'Platinum', 'Midnight Swirl',       82.50, false, DATE '2026-03-28'),
(1002, 'APAC', 'Gold',     'Midnight Swirl',       47.00, true,  DATE '2026-03-30'),
(1003, 'APAC', 'Silver',   'Midnight Papaya Halo', 23.75, false, DATE '2026-02-14'),
(1004, 'EMEA', 'Gold',     'Midnight Swirl',       55.20, false, DATE '2026-04-01'),
(1005, 'EMEA', 'Bronze',   'Arctic Basil Flow',    12.10, true,  DATE '2026-01-22'),
(1006, 'EMEA', 'Platinum', 'Midnight Swirl',       96.00, false, DATE '2026-04-03'),
(1007, 'AMER', 'Gold',     'Aura Berry Impact',    61.40, true,  DATE '2026-03-11'),
(1008, 'AMER', 'Silver',   'Midnight Swirl',       29.90, false, DATE '2026-03-19'),
(1009, 'AMER', 'Platinum', 'Midnight Swirl',       88.30, false, DATE '2026-04-02'),
(1010, 'APAC', 'Gold',     'Midnight Swirl',       44.65, true,  DATE '2026-03-27'),
(1011, 'EMEA', 'Silver',   'Midnight Swirl',       31.20, false, DATE '2026-03-05'),
(1012, 'AMER', 'Bronze',   'Midnight Papaya Halo', 15.00, false, DATE '2026-02-28'),
(1013, 'APAC', 'Platinum', 'Midnight Swirl',       74.80, false, DATE '2026-04-04'),
(1014, 'EMEA', 'Gold',     'Aura Berry Impact',    52.10, true,  DATE '2026-03-21'),
(1015, 'AMER', 'Gold',     'Midnight Swirl',       58.40, false, DATE '2026-03-30');
"

echo "== Create and seed mock sales_history in ${FQDS} =="
bq --location="${GCP_REGION}" --project_id="${GCP_PROJECT}" query --use_legacy_sql=false "
CREATE OR REPLACE TABLE \`${FQDS}.${FROYO_SALES_TABLE}\` (
  sale_date    DATE,
  product_name STRING,
  region       STRING,
  units_sold   INT64,
  revenue      FLOAT64
);

INSERT INTO \`${FQDS}.${FROYO_SALES_TABLE}\`
SELECT
  sale_date,
  'Midnight Swirl' AS product_name,
  region,
  units_sold,
  ROUND(units_sold * 6.50, 2) AS revenue
FROM (
  SELECT
    dt AS sale_date,
    r AS region,
    CAST(GREATEST(5, ROUND(
        40
      + 0.04 * DATE_DIFF(dt, DATE '2024-07-01', DAY)
      + 12   * SIN(2 * 3.141592653589793 * (MOD(EXTRACT(DAYOFWEEK FROM dt) + 5, 7) + 1) / 7.0)
      + (MOD(DATE_DIFF(dt, DATE '2024-07-01', DAY) * 17
          + CASE r WHEN 'APAC' THEN 3 WHEN 'EMEA' THEN 5 ELSE 7 END, 9) - 4)
      + (CASE r WHEN 'APAC' THEN 20 WHEN 'EMEA' THEN 10 ELSE 0 END)
    )) AS INT64) AS units_sold
  FROM UNNEST(GENERATE_DATE_ARRAY(DATE '2024-07-01', DATE '2026-06-30', INTERVAL 1 DAY)) AS dt
  CROSS JOIN UNNEST(['APAC', 'EMEA', 'AMER']) AS r
);
"

echo "✅ Mock AWS tables seeded successfully in BigQuery."
