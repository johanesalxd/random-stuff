"""PostgreSQL extractor using Spark JDBC.

Requires the PostgreSQL JDBC driver JAR to be available on the Spark
classpath. Pass it via --jars when submitting the batch:

    gcloud dataproc batches submit pyspark ... \\
        --jars=gs://<bucket>/jars/postgresql-42.7.3.jar

Or include it in jar_uris for a BQ Spark stored procedure.

Supports:
- Full table extraction
- Incremental extraction via a watermark column and GCP Secret Manager
- Parallel JDBC reads via partition_column / lower_bound / upper_bound
"""

import logging

from google.api_core.exceptions import NotFound
from google.cloud import bigquery as _bq
from pyspark.sql import DataFrame, SparkSession

from pipeline.config import ExtractionMode, PipelineConfig, resolve_secret
from pipeline.extractors.base import BaseExtractor

logger = logging.getLogger(__name__)

_JDBC_DRIVER = "org.postgresql.Driver"


class PostgresExtractor(BaseExtractor):
    """Extract data from a PostgreSQL database using Spark JDBC."""

    def extract(self, spark: SparkSession, config: PipelineConfig) -> DataFrame:
        """Extract data from Postgres.

        Args:
            spark: Active SparkSession.
            config: Pipeline configuration. config.source must be type=postgres.

        Returns:
            DataFrame with the extracted rows.
        """
        src = config.source
        jdbc_url = resolve_secret(src.jdbc_url_secret)

        base_options = {
            "url": jdbc_url,
            "driver": _JDBC_DRIVER,
            "fetchsize": str(src.fetch_size),
        }

        query = self._build_query(spark, config)
        logger.info(
            "Extracting from Postgres: source=%s db=%s tbl=%s mode=%s",
            config.source_name,
            config.db_name,
            config.tbl_name,
            config.extraction.mode,
        )

        if src.partition_column:
            # Parallel read -- requires lower_bound, upper_bound, num_partitions
            if src.lower_bound is None or src.upper_bound is None:
                raise ValueError(
                    "partition_column requires lower_bound and upper_bound "
                    "to be set in the source config."
                )
            options = {
                **base_options,
                "dbtable": f"({query}) AS _subq",
                "partitionColumn": src.partition_column,
                "lowerBound": str(src.lower_bound),
                "upperBound": str(src.upper_bound),
                "numPartitions": str(src.num_partitions),
            }
            logger.info(
                "Using parallel JDBC read: partitionColumn=%s partitions=%d",
                src.partition_column,
                src.num_partitions,
            )
        else:
            options = {
                **base_options,
                "dbtable": f"({query}) AS _subq",
            }

        return spark.read.format("jdbc").options(**options).load()

    def _build_query(self, spark: SparkSession, config: PipelineConfig) -> str:
        """Build the extraction SQL query.

        For incremental mode, appends a WHERE clause filtering on rows
        newer than the last recorded watermark.

        Args:
            spark: Active SparkSession (used to read the watermark from BQ).
            config: Pipeline configuration.

        Returns:
            SQL query string to pass to JDBC as a subquery.
        """
        src = config.source
        ext = config.extraction

        base_query = f"SELECT * FROM {src.table}"

        if ext.mode == ExtractionMode.INCREMENTAL:
            if not ext.watermark_column:
                raise ValueError(
                    "incremental mode requires watermark_column in the "
                    "extraction config."
                )
            last_watermark = self._read_watermark(spark, config)
            if last_watermark is not None:
                logger.info(
                    "Incremental extraction: watermark_column=%s last_value=%s",
                    ext.watermark_column,
                    last_watermark,
                )
                return f"{base_query} WHERE {ext.watermark_column} > '{last_watermark}'"
            logger.info(
                "No existing watermark found -- performing full extraction "
                "for incremental pipeline on first run."
            )

        return base_query

    def _read_watermark(
        self, spark: SparkSession, config: PipelineConfig
    ) -> str | None:
        """Read the last watermark value from BigQuery.

        Args:
            spark: Active SparkSession.
            config: Pipeline configuration.

        Returns:
            Last watermark value as a string, or None if no record exists.
        """
        ext = config.extraction
        tgt = config.target

        watermark_table = ext.watermark_table or (
            f"{tgt.project}.{tgt.dataset}._watermarks"
        )

        project = tgt.project
        query = f"""
            SELECT MAX(watermark_value) AS last_value
            FROM `{watermark_table}`
            WHERE source_name = '{config.source_name}'
              AND db_name = '{config.db_name}'
              AND tbl_name = '{config.tbl_name}'
        """
        try:
            bq_client = _bq.Client(project=project)
            rows = list(bq_client.query(query).result())
            if rows and rows[0]["last_value"] is not None:
                return rows[0]["last_value"]
            return None
        except NotFound:
            # Table doesn't exist yet — first run.
            return None
        except Exception:
            logger.warning(
                "Could not read watermark from %s -- treating as first run.",
                watermark_table,
                exc_info=True,
            )
            return None
