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
    Parameters are injected via SparkProcParamContext, which BigQuery
    populates from the arguments passed in the CALL statement.

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
    - When submitted as a Dataproc batch, Python executes this file as
      __main__ and CLI args are available via sys.argv.
    - When loaded by the BigQuery Spark runtime, the file is imported
      (not __main__). The BQ runtime makes `bigquery.spark.procedure`
      importable; we detect that with a try/except import rather than
      relying on an undocumented environment variable.
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

    The BQ Spark runtime makes `bigquery.spark.procedure` importable.
    Parameters are read from SparkProcParamContext, which BigQuery
    populates from the arguments passed in the CALL statement.

    A single SparkSession is obtained here and passed into run() so the
    pipeline does not attempt to create a second session.
    """
    from bigquery.spark.procedure import SparkProcParamContext  # noqa: PLC0415

    spark = SparkSession.builder.getOrCreate()
    ctx = SparkProcParamContext.getOrCreate(spark)

    run(
        source_name=ctx.source_name,
        db_name=ctx.db_name,
        tbl_name=ctx.tbl_name,
        gcs_bucket=ctx.gcs_bucket,
        run_id=getattr(ctx, "run_id", None),
        configs_prefix=getattr(ctx, "configs_prefix", "configs"),
        spark=spark,  # reuse -- do not create a second session
    )


# ---------------------------------------------------------------------------
# Execution mode detection
# ---------------------------------------------------------------------------
# Dataproc batch: Python runs this file as __main__ with sys.argv populated.
# BQ stored proc: the file is *imported*, not __main__. The BQ runtime makes
#   `bigquery.spark.procedure` available; we detect that with a try/except
#   import rather than an undocumented environment variable.

if __name__ == "__main__":
    _args = _parse_cli_args(sys.argv[1:])
    run(
        source_name=_args.source_name,
        db_name=_args.db_name,
        tbl_name=_args.tbl_name,
        gcs_bucket=_args.gcs_bucket,
        run_id=_args.run_id,
        configs_prefix=_args.configs_prefix,
    )
else:
    try:
        _run_as_bq_stored_proc()
    except ImportError:
        # Not running inside the BQ Spark runtime -- module was imported for
        # testing or other tooling. Do nothing.
        pass
