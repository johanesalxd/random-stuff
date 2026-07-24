# Froyo cross-cloud lakehouse — agent instructions (optional VS Code path)

Drop this into `.github/copilot-instructions.md` of a VS Code workspace (with the
Google Cloud Data Agent Kit) to reproduce the keynote's agentic experience on top
of this repo. Replace the placeholders with your `config.local.env` values.

## 1. Project context
- **Project ID**: `<GCP_PROJECT>`
- **Region**: `<GCP_REGION>` (e.g. `us-east4`)
- **Domain**: "Froyo", a frozen-yogurt brand. The hero product is **Midnight Swirl**.
- **Raw docs**: recipe/supplier PDFs live in `gs://<GCS_PDF_BUCKET>`.

## 2. Data locations
- **Allergen / recipe / product knowledge** (native BigQuery, extracted from PDFs):
  dataset `<GCP_PROJECT>.<FROYO_NATIVE_DATASET>` — tables `products`, `recipes`,
  `ingredient_allergens`, view `product_allergens`.
- **Customer loyalty + sales history** (Apache Iceberg, physically in **AWS S3/Glue**,
  federated into BigQuery via cross-cloud Lakehouse):
  `<GCP_PROJECT>.<FEDERATED_CATALOG>.<GLUE_DATABASE>.global_loyalty` and
  `...<GLUE_DATABASE>.sales_history`.

## 3. Rules
- **CRITICAL — cross-cloud joins run in BigQuery.** The loyalty/sales tables are
  AWS-resident but queryable directly from BigQuery. Join them with the native
  knowledge tables using ordinary BigQuery SQL; do not copy/move data.
- **CRITICAL — allergen safety.** Midnight Base 204 contains **Soy** (per
  `midnight_base_204_manual.pdf`). Any Midnight Swirl customer-targeting must
  exclude `soy_sensitive_flag = TRUE` customers.
- **Forecasting** uses BigQuery ML `ARIMA_PLUS` on the federated `sales_history`
  table (see `gcp/50_forecast_bqml.sh`). Serverless Spark / Lightning Engine is an
  optional later upgrade for the same result.
