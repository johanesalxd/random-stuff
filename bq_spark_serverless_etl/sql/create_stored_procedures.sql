-- BigQuery Spark Stored Procedure definitions
--
-- Run this file once to register the procedures in BigQuery.
-- After that, any tool that can issue CALL statements (Dataform, dbt,
-- Cloud Composer, bq CLI) can trigger the pipeline.
--
-- Prerequisites:
--   1. A Spark connection must exist in the same region as the procedures.
--      Create one with:
--        bq mk --connection \
--          --connection_type=SPARK \
--          --project_id=MY_PROJECT \
--          --location=MY_REGION \
--          MY_CONNECTION_NAME
--
--   2. The connection's service account must have:
--        - roles/storage.objectViewer   on the GCS bucket (to read main.py + wheel)
--        - roles/secretmanager.secretAccessor  (to resolve JDBC URL secrets)
--        - roles/bigquery.dataEditor    on target datasets
--
--   3. Replace all <...> placeholders before running.
--
-- Run with:
--   bq query --project_id=<MY_PROJECT> --nouse_legacy_sql < sql/create_stored_procedures.sql

-- ---------------------------------------------------------------------------
-- Generic pipeline procedure
-- ---------------------------------------------------------------------------
-- Accepts any source/table combination and dispatches to the correct
-- extractor via the registry in pipeline/registry.py.
--
-- Parameters:
--   source_name     Logical source group (maps to a configs/ top-level folder)
--   db_name         Database or schema name
--   tbl_name        Table name
--   gcs_bucket      GCS bucket where pipeline configs and wheels are stored
--   run_id          Unique run identifier (pass GENERATE_UUID() from callers)

CREATE OR REPLACE PROCEDURE `<MY_PROJECT>.<MY_DATASET>.run_pipeline`(
    IN source_name  STRING,
    IN db_name      STRING,
    IN tbl_name     STRING,
    IN gcs_bucket   STRING,
    IN run_id       STRING
)
WITH CONNECTION `<MY_PROJECT>.<MY_REGION>.<MY_CONNECTION_NAME>`
OPTIONS (
    engine          = "SPARK",
    runtime_version = "2.3",

    -- Entry point: the pipeline main script in GCS.
    main_file_uri   = "gs://<MY_GCS_BUCKET>/pipeline/main.py",

    -- Python wheel containing the pipeline package.
    -- Rebuild and re-upload after any code change.
    py_file_uris    = ["gs://<MY_GCS_BUCKET>/wheels/pipeline-0.1.0-py3-none-any.whl"],

    -- PostgreSQL JDBC driver (required only for postgres source type).
    -- Download: https://jdbc.postgresql.org/download/postgresql-42.7.3.jar
    jar_uris        = ["gs://<MY_GCS_BUCKET>/jars/postgresql-42.7.3.jar"],

    -- Spark properties.
    --
    -- spark.pyspark.python.pip.packages: installs packages not present in the
    -- Dataproc Serverless 2.x default Conda env (pydantic, google-cloud-secret-manager,
    -- google-cloud-storage, pyyaml). Without this the pipeline will crash on import.
    --
    -- spark.dataproc.scaling.version=2: enables improved autoscaling heuristics.
    properties      = [
        ("spark.pyspark.python.pip.packages",
            "pydantic==2.13.0,google-cloud-secret-manager==2.16.0,google-cloud-storage==2.10.0,pyyaml==6.0.2"),
        ("spark.dataproc.scaling.version", "2"),
        ("spark.executor.cores",           "4"),
        ("spark.driver.memory",            "4g")
    ]
)
LANGUAGE PYTHON;

-- ---------------------------------------------------------------------------
-- Usage examples
-- ---------------------------------------------------------------------------

-- Direct invocation from BigQuery console or bq CLI:
--
--   CALL `<MY_PROJECT>.<MY_DATASET>.run_pipeline`(
--       'thelook',
--       'public',
--       'orders',
--       'my-config-bucket',
--       GENERATE_UUID()
--   );

-- ---------------------------------------------------------------------------
-- Dataform integration (.sqlx)
-- ---------------------------------------------------------------------------
-- In your Dataform repository, create a file such as:
--
--   definitions/ingestion/thelook_orders.sqlx
--
-- with the following content:
--
--   config {
--     type: "operations",
--     hasOutput: false,
--     tags: ["ingestion"],
--     dependencies: []
--   }
--
--   CALL `${dataform.projectConfig.defaultDatabase}.<MY_DATASET>.run_pipeline`(
--       'thelook',
--       'public',
--       'orders',
--       'my-config-bucket',
--       GENERATE_UUID()
--   );
--
-- Dataform will execute this as a BigQuery job within the workflow DAG,
-- and downstream SQL models can declare it as a dependency via `dependencies`.

-- ---------------------------------------------------------------------------
-- Cloud Composer / Airflow integration
-- ---------------------------------------------------------------------------
-- Use the BigQueryInsertJobOperator to CALL the procedure from Airflow:
--
--   BigQueryInsertJobOperator(
--       task_id="ingest_thelook_orders",
--       configuration={
--           "query": {
--               "query": """
--                   CALL `my-project.my_dataset.run_pipeline`(
--                       'thelook', 'public', 'orders',
--                       'my-config-bucket', '{{ run_id }}'
--                   )
--               """,
--               "useLegacySql": False,
--           }
--       },
--   )
