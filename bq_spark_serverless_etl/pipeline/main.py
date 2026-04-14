"""Pipeline entry point.

Supports two execution modes transparently:

Mode 1 -- Dataproc Serverless Batch (direct CLI submission):
    Reads parameters from command-line arguments (argparse).

    gcloud dataproc batches submit pyspark gs://<bucket>/pipeline/main.py \\
        --region=<region> \\
        --py-files=gs://<bucket>/wheels/pipeline-0.1.0-py3-none-any.whl \\
        --jars=gs://<bucket>/jars/postgresql-42.7.3.jar \\
        -- \\
        --source_name=mydb \\
        --db_name=public \\
        --tbl_name=users \\
        --gcs_bucket=my-config-bucket

Mode 2 -- BigQuery Spark Stored Procedure (callable from Dataform or SQL):
    Parameters are read from BIGQUERY_PROC_PARAM.* environment variables,
    which BigQuery injects at runtime from the arguments passed in the CALL
    statement.

    The procedure is created once with:
        CREATE OR REPLACE PROCEDURE `project.dataset.run_pipeline`(
            IN source_name STRING,
            IN db_name     STRING,
            IN tbl_name    STRING,
            IN gcs_bucket  STRING,
            IN run_id      STRING
        )
        WITH CONNECTION `project.region.connection`
        OPTIONS(
            engine="SPARK",
            runtime_version="2.3",
            main_file_uri="gs://<bucket>/pipeline/main.py",
            py_file_uris=["gs://<bucket>/wheels/pipeline-0.1.0-py3-none-any.whl"],
            jar_uris=["gs://<bucket>/jars/postgresql-42.7.3.jar"]
        )
        LANGUAGE PYTHON;

    Called from Dataform or any SQL client:
        CALL `project.dataset.run_pipeline`(
            'mydb', 'public', 'users', 'my-config-bucket', GENERATE_UUID()
        );

Execution mode detection:
    - Both modes run this file as __main__ (BQ Spark runs main_file_uri
      directly, not as an import).
    - We detect the mode by checking for the BIGQUERY_PROC_PARAM env var
      prefix that BQ Spark injects at runtime. This is more reliable than
      attempting to import bigquery.spark.procedure, which can fail with
      TypeError due to protobuf version mismatches in bigspark.zip.
"""

import argparse
import logging
import sys

from pyspark.sql import SparkSession

from pipeline.config import load_config
from pipeline.registry import get_extractor, get_writer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def run(
    source_name: str,
    db_name: str,
    tbl_name: str,
    gcs_bucket: str,
    run_id: str | None = None,
    configs_prefix: str = "configs",
    spark: SparkSession | None = None,
) -> None:
    """Core pipeline logic -- framework-agnostic.

    Args:
        source_name: Logical source group name (top-level config folder).
        db_name: Database or schema name.
        tbl_name: Table name.
        gcs_bucket: GCS bucket name where configs are stored.
        run_id: Optional unique identifier for this pipeline run (for logging).
        configs_prefix: Prefix inside gcs_bucket for config files.
        spark: Optional SparkSession. Created via getOrCreate() if not provided.
            Pass an existing session when the caller (e.g. BQ stored proc path)
            already holds a reference to avoid creating a second session.
    """
    run_label = f"{source_name}/{db_name}/{tbl_name}"
    logger.info("Pipeline run started: %s run_id=%s", run_label, run_id or "unset")

    if spark is None:
        spark = SparkSession.builder.appName(f"pipeline-{run_label}").getOrCreate()

    config = load_config(
        source_name=source_name,
        db_name=db_name,
        tbl_name=tbl_name,
        gcs_bucket=gcs_bucket,
        configs_prefix=configs_prefix,
    )

    extractor = get_extractor(config.source.type)
    writer = get_writer()  # always BigQuery for now

    df = extractor.extract(spark, config)
    writer.write(df, config)

    logger.info("Pipeline run completed: %s run_id=%s", run_label, run_id or "unset")


def _parse_cli_args(argv: list[str]) -> argparse.Namespace:
    """Parse command-line arguments for Dataproc Serverless submission."""
    parser = argparse.ArgumentParser(
        description="GCP Spark batch pipeline: extract from source, load to BigQuery."
    )
    parser.add_argument(
        "--source_name",
        required=True,
        help="Logical source group name (e.g. mydb).",
    )
    parser.add_argument(
        "--db_name",
        required=True,
        help="Database or schema name (e.g. public).",
    )
    parser.add_argument(
        "--tbl_name",
        required=True,
        help="Table name (e.g. users).",
    )
    parser.add_argument(
        "--gcs_bucket",
        required=True,
        help="GCS bucket name where pipeline configs are stored.",
    )
    parser.add_argument(
        "--run_id",
        default=None,
        help="Optional unique run identifier for tracing.",
    )
    parser.add_argument(
        "--configs_prefix",
        default="configs",
        help="Prefix inside --gcs_bucket where YAML configs live.",
    )
    return parser.parse_args(argv)


def _run_as_bq_stored_proc() -> None:
    """Entry point when called from a BigQuery Spark stored procedure.

    Reads parameters from BIGQUERY_PROC_PARAM.<name> environment variables
    (Method 1 from the BQ Spark docs). Values are JSON-encoded strings.

    Using env vars directly instead of importing bigquery.spark.procedure
    (SparkProcParamContext) avoids a protobuf version mismatch that occurs
    between the Dataproc Serverless conda env and the bigspark.zip bundled
    with the BQ Spark runtime.

    Reference:
      https://cloud.google.com/bigquery/docs/spark-procedures#pass-input-parameter
    """
    import json as _json  # noqa: PLC0415
    import os as _os  # noqa: PLC0415

    def _param(name: str, default: str | None = None) -> str | None:
        raw = _os.environ.get(f"BIGQUERY_PROC_PARAM.{name}")
        if raw is None:
            return default
        return _json.loads(raw)

    spark = SparkSession.builder.getOrCreate()

    run(
        source_name=_param("source_name"),
        db_name=_param("db_name"),
        tbl_name=_param("tbl_name"),
        gcs_bucket=_param("gcs_bucket"),
        run_id=_param("run_id"),
        configs_prefix=_param("configs_prefix", "configs"),
        spark=spark,
    )


# ---------------------------------------------------------------------------
# Execution mode detection
# ---------------------------------------------------------------------------
# Both modes run this file as __main__ (BQ Spark executes main_file_uri
# directly). Detect mode via BIGQUERY_PROC_PARAM.* env vars that BQ Spark
# injects at runtime -- one per procedure IN parameter.

if __name__ == "__main__":
    # BQ Spark injects procedure parameters as env vars with the prefix
    # BIGQUERY_PROC_PARAM. Use that as a reliable mode signal rather than
    # relying on import side-effects which can fail for unrelated reasons
    # (e.g. protobuf version mismatches in bigspark.zip).
    import os as _os  # noqa: PLC0415

    _in_bq_spark = any(k.startswith("BIGQUERY_PROC_PARAM") for k in _os.environ)

    if _in_bq_spark:
        _run_as_bq_stored_proc()
    else:
        # Dataproc Serverless batch mode -- parameters come from CLI args.
        _args = _parse_cli_args(sys.argv[1:])
        run(
            source_name=_args.source_name,
            db_name=_args.db_name,
            tbl_name=_args.tbl_name,
            gcs_bucket=_args.gcs_bucket,
            run_id=_args.run_id,
            configs_prefix=_args.configs_prefix,
        )
