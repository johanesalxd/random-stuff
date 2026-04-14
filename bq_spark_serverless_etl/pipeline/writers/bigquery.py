"""BigQuery writer using the Spark BigQuery connector.

Supports three write modes:

- overwrite: Truncate and replace the target table on every run.
- append:    Add new rows to the target table without removing existing ones.
- merge:     Upsert rows using user-defined merge_keys. Existing rows whose
             merge key matches an incoming row are updated; non-matching
             incoming rows are inserted. Implemented via a BQ MERGE DML
             statement executed after staging the incoming data to a
             temporary table.

Partitioning and clustering are applied on first write (table creation).
On subsequent writes BigQuery preserves the existing configuration.

Reference:
  https://cloud.google.com/dataproc/docs/guides/bigquery-connector-spark-example
"""

import logging
from datetime import datetime, timezone

from pyspark.sql import DataFrame, SparkSession

from pipeline.config import ExtractionMode, PipelineConfig, WriteMode
from pipeline.writers.base import BaseWriter

logger = logging.getLogger(__name__)

# Staging dataset used for merge temp tables. Reuse the target dataset by
# default so no cross-dataset permissions are needed.
_STAGING_TABLE_TTL_HOURS = 1


class BigQueryWriter(BaseWriter):
    """Write a Spark DataFrame to a BigQuery table."""

    def write(self, df: DataFrame, config: PipelineConfig) -> None:
        """Write data to BigQuery and (for incremental runs) update the watermark.

        Args:
            df: DataFrame to write.
            config: Pipeline configuration. config.target defines the
                destination table, write mode, partitioning, and clustering.
        """
        tgt = config.target
        spark = df.sparkSession

        logger.info(
            "Writing to BigQuery: table=%s mode=%s",
            tgt.full_table_id,
            tgt.write_mode,
        )

        if tgt.write_mode == WriteMode.OVERWRITE:
            self._write_overwrite(df, config)

        elif tgt.write_mode == WriteMode.APPEND:
            self._write_append(df, config)

        elif tgt.write_mode == WriteMode.MERGE:
            self._write_merge(df, config, spark)

        logger.info("Successfully wrote to BigQuery table: %s", tgt.full_table_id)

        # Write-back watermark for incremental pipelines so the next run
        # only extracts rows newer than the current batch's maximum value.
        if config.extraction.mode == ExtractionMode.INCREMENTAL:
            self._update_watermark(df, config, spark)

    # ------------------------------------------------------------------
    # Write mode implementations
    # ------------------------------------------------------------------

    def _base_writer(self, df: DataFrame, config: PipelineConfig):
        """Build a DataFrameWriter with shared options applied."""
        tgt = config.target
        writer = (
            df.write.format("bigquery")
            .option("writeMethod", "direct")
            .option("table", tgt.full_table_id)
        )
        if tgt.partition_field:
            writer = writer.option("partitionField", tgt.partition_field)
            logger.info("BQ partitioning on: %s", tgt.partition_field)
        if tgt.clustering_fields:
            writer = writer.option("clusteredFields", ",".join(tgt.clustering_fields))
            logger.info("BQ clustering on: %s", tgt.clustering_fields)
        return writer

    def _write_overwrite(self, df: DataFrame, config: PipelineConfig) -> None:
        self._base_writer(df, config).mode("overwrite").save()

    def _write_append(self, df: DataFrame, config: PipelineConfig) -> None:
        self._base_writer(df, config).mode("append").save()

    def _write_merge(
        self, df: DataFrame, config: PipelineConfig, spark: SparkSession
    ) -> None:
        """Upsert via BigQuery MERGE DML.

        Strategy:
        1. Write the incoming DataFrame to a short-lived staging table
           (overwrite, same dataset as target).
        2. Execute a MERGE statement that updates matching rows and
           inserts new ones based on merge_keys.
        3. Drop the staging table.

        This avoids loading the full DataFrame into driver memory and keeps
        the merge logic inside BigQuery where it is most efficient.

        Args:
            df: Incoming DataFrame.
            config: Pipeline configuration.
            spark: Active SparkSession (used to run BQ DML via bigquery format).
        """
        tgt = config.target
        run_ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        staging_table = f"{tgt.project}.{tgt.dataset}._staging_{tgt.table}_{run_ts}"

        logger.info(
            "Merge: staging to temp table %s before MERGE into %s",
            staging_table,
            tgt.full_table_id,
        )

        # Step 1: write incoming data to staging table (overwrite ensures idempotency)
        (
            df.write.format("bigquery")
            .option("writeMethod", "direct")
            .option("table", staging_table)
            .mode("overwrite")
            .save()
        )

        # Step 2: build and execute MERGE DML
        merge_keys = config.target.merge_keys
        columns = df.columns

        on_clause = " AND ".join(f"T.`{k}` = S.`{k}`" for k in merge_keys)
        non_key_columns = [c for c in columns if c not in merge_keys]
        update_clause = ", ".join(f"T.`{c}` = S.`{c}`" for c in non_key_columns)
        insert_cols = ", ".join(f"`{c}`" for c in columns)
        insert_vals = ", ".join(f"S.`{c}`" for c in columns)

        # If every column is a merge key there is nothing to update; omit
        # WHEN MATCHED entirely to avoid an empty UPDATE SET clause (invalid SQL).
        matched_clause = (
            f"WHEN MATCHED THEN\n                UPDATE SET {update_clause}\n            "
            if non_key_columns
            else ""
        )

        merge_sql = f"""
            MERGE `{tgt.full_table_id}` AS T
            USING `{staging_table}` AS S
            ON {on_clause}
            {matched_clause}WHEN NOT MATCHED THEN
                INSERT ({insert_cols})
                VALUES ({insert_vals})
        """
        logger.info("Executing MERGE DML for table: %s", tgt.full_table_id)

        # Run DML via the BigQuery connector's query option
        spark.read.format("bigquery").option("query", merge_sql).load()

        # Step 3: clean up staging table
        drop_sql = f"DROP TABLE IF EXISTS `{staging_table}`"
        spark.read.format("bigquery").option("query", drop_sql).load()
        logger.info("Dropped staging table: %s", staging_table)

    # ------------------------------------------------------------------
    # Watermark management
    # ------------------------------------------------------------------

    def _update_watermark(
        self, df: DataFrame, config: PipelineConfig, spark: SparkSession
    ) -> None:
        """Persist the new high-watermark value to BigQuery after a successful write.

        The watermark table has schema:
            source_name     STRING NOT NULL,
            db_name         STRING NOT NULL,
            tbl_name        STRING NOT NULL,
            watermark_value STRING NOT NULL,
            updated_at      TIMESTAMP NOT NULL

        On each incremental run, we upsert the row for this pipeline's
        identity tuple so the next run starts from the correct position.

        Args:
            df: The DataFrame that was just written (used to compute MAX watermark).
            config: Pipeline configuration.
            spark: Active SparkSession.
        """
        ext = config.extraction
        tgt = config.target

        if not ext.watermark_column:
            return

        watermark_table = ext.watermark_table or (
            f"{tgt.project}.{tgt.dataset}._watermarks"
        )

        # Compute the maximum value of the watermark column in this batch.
        # Cast to string for uniform storage regardless of column type
        # (timestamp, date, integer).
        max_row = df.selectExpr(
            f"CAST(MAX(`{ext.watermark_column}`) AS STRING) AS max_wm"
        ).first()

        if max_row is None or max_row["max_wm"] is None:
            logger.warning(
                "Could not compute max watermark from column '%s' -- skipping write-back.",
                ext.watermark_column,
            )
            return

        new_watermark = max_row["max_wm"]
        now_ts = datetime.now(timezone.utc).isoformat()

        logger.info(
            "Updating watermark: table=%s source=%s/%s/%s column=%s new_value=%s",
            watermark_table,
            config.source_name,
            config.db_name,
            config.tbl_name,
            ext.watermark_column,
            new_watermark,
        )

        merge_sql = f"""
            MERGE `{watermark_table}` AS T
            USING (
                SELECT
                    '{config.source_name}' AS source_name,
                    '{config.db_name}'     AS db_name,
                    '{config.tbl_name}'    AS tbl_name,
                    '{new_watermark}'      AS watermark_value,
                    TIMESTAMP '{now_ts}'   AS updated_at
            ) AS S
            ON  T.source_name = S.source_name
            AND T.db_name     = S.db_name
            AND T.tbl_name    = S.tbl_name
            WHEN MATCHED THEN
                UPDATE SET
                    T.watermark_value = S.watermark_value,
                    T.updated_at      = S.updated_at
            WHEN NOT MATCHED THEN
                INSERT (source_name, db_name, tbl_name, watermark_value, updated_at)
                VALUES (S.source_name, S.db_name, S.tbl_name, S.watermark_value, S.updated_at)
        """

        try:
            spark.read.format("bigquery").option("query", merge_sql).load()
            logger.info("Watermark updated to: %s", new_watermark)
        except Exception:
            # A watermark write failure must not fail the overall pipeline run.
            # The worst case is the next run re-extracts some already-loaded rows
            # (duplicate delivery), which is acceptable in an at-least-once model.
            logger.error(
                "Failed to update watermark -- next incremental run may re-extract rows.",
                exc_info=True,
            )
