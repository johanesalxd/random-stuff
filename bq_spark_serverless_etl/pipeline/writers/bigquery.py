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

from google.api_core.exceptions import NotFound
from google.cloud import bigquery as _bq
from pyspark.sql import DataFrame

from pipeline.config import PipelineConfig
from pipeline.writers.base import BaseWriter

logger = logging.getLogger(__name__)


class BigQueryWriter(BaseWriter):
    """Write a Spark DataFrame to a BigQuery table."""

    def write(self, df: DataFrame, config: PipelineConfig) -> None:
        """Write data to BigQuery and (for incremental runs) update the watermark.

        Args:
            df: DataFrame to write.
            config: Pipeline configuration.
        """
        logger.info(
            "Writing to BigQuery: table=%s mode=%s",
            config.full_table_id,
            config.write_mode,
        )

        if config.write_mode == "overwrite":
            self._write_overwrite(df, config)

        elif config.write_mode == "append":
            self._write_append(df, config)

        elif config.write_mode == "merge":
            self._write_merge(df, config)

        logger.info("Successfully wrote to BigQuery table: %s", config.full_table_id)

        # Write-back watermark for incremental pipelines so the next run
        # only extracts rows newer than the current batch's maximum value.
        if config.extraction_mode == "incremental":
            self._update_watermark(df, config)

    # ------------------------------------------------------------------
    # Write mode implementations
    # ------------------------------------------------------------------

    def _base_writer(self, df: DataFrame, config: PipelineConfig):
        """Build a DataFrameWriter with shared options applied."""
        writer = (
            df.write.format("bigquery")
            .option("writeMethod", "direct")
            .option("table", config.full_table_id)
        )
        if config.partition_field:
            writer = writer.option("partitionField", config.partition_field)
            logger.info("BQ partitioning on: %s", config.partition_field)
        if config.clustering_fields:
            writer = writer.option(
                "clusteredFields", ",".join(config.clustering_fields)
            )
            logger.info("BQ clustering on: %s", config.clustering_fields)
        return writer

    def _write_overwrite(self, df: DataFrame, config: PipelineConfig) -> None:
        self._base_writer(df, config).mode("overwrite").save()

    def _write_append(self, df: DataFrame, config: PipelineConfig) -> None:
        self._base_writer(df, config).mode("append").save()

    def _write_merge(self, df: DataFrame, config: PipelineConfig) -> None:
        """Upsert via BigQuery MERGE DML.

        On first run (target table absent) falls back to a direct overwrite so
        that partitioning and clustering are applied correctly via _base_writer.

        On subsequent runs:
        1. Write the incoming DataFrame to a short-lived staging table
           (overwrite, same dataset as target).
        2. Execute a MERGE statement that updates matching rows and
           inserts new ones based on merge_keys.
        3. Drop the staging table.

        Args:
            df: Incoming DataFrame.
            config: Pipeline configuration.
        """
        # Check whether target table exists before staging anything.
        bq_client = _bq.Client(project=config.project)
        try:
            bq_client.get_table(config.full_table_id)
        except NotFound:
            logger.info(
                "Target table %s does not exist -- falling back to overwrite"
                " for initial load.",
                config.full_table_id,
            )
            self._write_overwrite(df, config)
            return

        run_ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        staging_table = (
            f"{config.project}.{config.dataset}._staging_{config.table}_{run_ts}"
        )

        logger.info(
            "Merge: staging to temp table %s before MERGE into %s",
            staging_table,
            config.full_table_id,
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
        merge_keys = config.merge_keys
        columns = df.columns

        on_clause = " AND ".join(f"T.`{k}` = S.`{k}`" for k in merge_keys)
        non_key_columns = [c for c in columns if c not in merge_keys]
        update_clause = ", ".join(f"T.`{c}` = S.`{c}`" for c in non_key_columns)
        insert_cols = ", ".join(f"`{c}`" for c in columns)
        insert_vals = ", ".join(f"S.`{c}`" for c in columns)

        # If every column is a merge key there is nothing to update; omit
        # WHEN MATCHED entirely to avoid an empty UPDATE SET clause (invalid SQL).
        matched_clause = (
            "WHEN MATCHED THEN\n"
            f"                UPDATE SET {update_clause}\n            "
            if non_key_columns
            else ""
        )

        merge_sql = f"""
            MERGE `{config.full_table_id}` AS T
            USING `{staging_table}` AS S
            ON {on_clause}
            {matched_clause}WHEN NOT MATCHED THEN
                INSERT ({insert_cols})
                VALUES ({insert_vals})
        """
        logger.info("Executing MERGE DML for table: %s", config.full_table_id)

        # Run DML via the BigQuery Python client (the Spark BQ connector's
        # "query" option is for SELECT reads only, not DML).
        bq_client.query(merge_sql).result()

        # Step 3: clean up staging table
        drop_sql = f"DROP TABLE IF EXISTS `{staging_table}`"
        bq_client.query(drop_sql).result()
        logger.info("Dropped staging table: %s", staging_table)

    # ------------------------------------------------------------------
    # Watermark management
    # ------------------------------------------------------------------

    def _update_watermark(self, df: DataFrame, config: PipelineConfig) -> None:
        """Persist the new high-watermark value to BigQuery after a successful write.

        The watermark table has schema:
            source_name     STRING NOT NULL,
            db_name         STRING NOT NULL,
            tbl_name        STRING NOT NULL,
            watermark_value STRING NOT NULL,
            updated_at      TIMESTAMP NOT NULL

        On each incremental run, upserts the row for this pipeline's
        identity tuple so the next run starts from the correct position.

        Args:
            df: The DataFrame that was just written (used to compute MAX watermark).
            config: Pipeline configuration.
        """
        if not config.watermark_column:
            return

        watermark_table = f"{config.project}.{config.dataset}._watermarks"

        # Compute the maximum value of the watermark column in this batch.
        # Cast to string for uniform storage regardless of column type
        # (timestamp, date, integer).
        max_row = df.selectExpr(
            f"CAST(MAX(`{config.watermark_column}`) AS STRING) AS max_wm"
        ).first()

        if max_row is None or max_row["max_wm"] is None:
            logger.warning(
                "Could not compute max watermark from column '%s'"
                " -- skipping write-back.",
                config.watermark_column,
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
            config.watermark_column,
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
                VALUES (S.source_name, S.db_name, S.tbl_name,
                        S.watermark_value, S.updated_at)
        """

        create_sql = f"""
            CREATE TABLE IF NOT EXISTS `{watermark_table}` (
                source_name     STRING NOT NULL,
                db_name         STRING NOT NULL,
                tbl_name        STRING NOT NULL,
                watermark_value STRING NOT NULL,
                updated_at      TIMESTAMP NOT NULL
            )
        """

        try:
            bq_client = _bq.Client(project=config.project)
            bq_client.query(create_sql).result()
            bq_client.query(merge_sql).result()
            logger.info("Watermark updated to: %s", new_watermark)
        except Exception:
            # A watermark write failure must not fail the overall pipeline run.
            # The worst case is the next run re-extracts some already-loaded rows
            # (duplicate delivery), which is acceptable in an at-least-once model.
            logger.error(
                "Failed to update watermark -- next incremental run"
                " may re-extract rows.",
                exc_info=True,
            )
