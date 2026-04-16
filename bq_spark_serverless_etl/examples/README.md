# Quickstart: Postgres → BigQuery via Serverless Spark

A self-contained notebook that reads a Postgres table and writes it to BigQuery using Dataproc Serverless Spark — no config files, no pipeline framework, no orchestration required.

## What it demonstrates

```
Cloud SQL Postgres
      │
      │  JDBC (Spark reads remotely)
      ▼
Dataproc Serverless Spark  ←── spun up from BQ Studio notebook
      │
      │  BigQuery connector (writeMethod=direct, notebook default)
      ▼
BigQuery  raw_thelook.orders_quickstart
```

The notebook is the whole pipeline. Change one variable to read a different table.

> **Write method note:** This notebook uses `writeMethod=direct` (Storage Write API) because it is the BQ Studio default and requires no configuration. The production pipeline (`pipeline/main.py`) uses `writeMethod=indirect` (GCS staging → BQ load job), which is free for batch workloads and the recommended approach at scale. See Cell 6 in the notebook for details.

## Prerequisites

Provision the demo infrastructure and seed the database:

```bash
GCP_PROJECT=my-project GCP_REGION=us-central1 make infra-up
make seed
```

This creates the GCS bucket, Cloud SQL instance, Secret Manager secret, BQ datasets, and the `spark-etl-sa` service account that the Spark session runs as.

## Running in BigQuery Studio

1. Open [BigQuery Studio](https://console.cloud.google.com/bigquery).
2. Click **+** → **Notebook** to create a new Python notebook.
3. Upload `quickstart.ipynb` via **File → Upload**, or paste cells manually.
4. Edit **Cell 1** — set `PROJECT`, `REGION`, `GCS_BUCKET`, and optionally `POSTGRES_TABLE` / `BQ_TABLE`.
5. Run all cells top to bottom. Cell 3 (session creation) takes ~60–90 seconds.

> **Note on runtime:** BQ Studio notebooks require a Vertex AI runtime with Python 3.11. If you see a `PYTHON_VERSION_MISMATCH` error, recreate the runtime with Python 3.11 in the [Runtimes page](https://console.cloud.google.com/vertex-ai/colab/runtimes).

## Notebook structure

| Cell | What it does |
|------|-------------|
| 1 | **Config** — set project, region, bucket, table, destination |
| 2 | **Upload JDBC JAR** — downloads PostgreSQL driver and uploads to GCS (skipped if already present) |
| 3 | **Create Spark session** — starts a Dataproc Serverless cluster via Spark Connect |
| 4 | **Read Postgres** — fetches JDBC URL from Secret Manager, reads table into a Spark DataFrame |
| 5 | **Preview** — `printSchema()`, `show()`, `count()` |
| 6 | **Write to BigQuery** — `CREATE OR REPLACE TABLE` via the Spark BQ connector |
| 7 | **Verify** — reads the BQ table back to confirm |
| 8 | **Stop session** — releases Dataproc Serverless resources |

## Changing the source table

In Cell 1, change `POSTGRES_TABLE` and `BQ_TABLE`:

```python
POSTGRES_TABLE = "public.users"        # or public.order_items
BQ_TABLE       = "users_quickstart"
```

Re-run from Cell 4 (no need to restart the Spark session).

## IAM requirements

Your user account needs:

| Role | Why |
|------|-----|
| `roles/dataproc.editor` | Create Spark sessions |
| `roles/bigquery.studioUser` | Use BQ Studio notebooks |
| `roles/iam.serviceAccountUser` on `spark-etl-sa` | Impersonate the session SA |

The `spark-etl-sa` service account (created by `infra/setup.sh`) has all permissions the Spark session needs: Cloud SQL access, Secret Manager, GCS, BigQuery read/write.

## Converting to a batch job

To run as a non-interactive Dataproc Serverless batch (e.g. for scheduling):

1. Download the notebook as `.py` via **File → Download → Download .py**.
2. Replace the session creation block:
   ```python
   # Remove:
   from google.cloud.dataproc_spark_connect import DataprocSparkSession
   from google.cloud.dataproc_v1 import Session
   session = Session()
   ...
   spark = DataprocSparkSession.builder...getOrCreate()

   # Replace with:
   from pyspark.sql import SparkSession
   spark = SparkSession.builder.appName("postgres-to-bq").getOrCreate()
   ```
3. Submit:
   ```bash
   gcloud dataproc batches submit pyspark quickstart.py \
       --region=us-central1 \
       --service-account=spark-etl-sa@PROJECT.iam.gserviceaccount.com \
       --jars=gs://BUCKET/jars/postgresql-42.7.3.jar \
       --properties=spark.pyspark.python.pip.packages=google-cloud-secret-manager==2.16.0
   ```
