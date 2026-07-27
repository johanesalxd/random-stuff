#!/usr/bin/env python3
"""Step 2: upload Parquet to GCS and load it into a partitioned/clustered BQ table.

Authentication is your current gcloud/ADC login; no service-account keys are used.

Flow:
    local .parquet --(upload)--> gs://BUCKET/PREFIX/ --(load job)--> BigQuery

Notes:
    * source_format=PARQUET: BigQuery reads the schema straight from the file.
    * The target table is time-partitioned on `date` and clustered on sym/type,
      matching PARTITION BY date in the customer DDL.
    * All Parquet columns load as NULLABLE, matching a "keep the original
      (mostly-null) schema" migration.

Run:
    uv run python 02_load_bigquery.py
"""

from __future__ import annotations

import logging

from google.cloud import bigquery, storage

import config
from schema import bq_clustering_columns, partition_column

logger = logging.getLogger(__name__)

PROJECT = config.resolve_gcp_project()


def upload_to_gcs() -> list[str]:
    """Upload local Parquet files to GCS.

    Returns:
        The list of ``gs://`` URIs uploaded.

    Raises:
        SystemExit: If GCS_BUCKET is unset or no Parquet files are found.
    """
    if not config.GCS_BUCKET:
        raise SystemExit("Set GCS_BUCKET in .env first.")
    client = storage.Client(project=PROJECT)
    bucket = client.bucket(config.GCS_BUCKET)
    parquet_files = [
        config.PARQUET_DIR / f"{config.BQ_TABLE}__{day}.parquet"
        for day in config.POC_DATES
    ]
    missing = [path.name for path in parquet_files if not path.is_file()]
    if missing:
        raise SystemExit(f"Missing Parquet files: {', '.join(missing)}")

    uris = []
    for pq_file in parquet_files:
        blob_name = f"{config.GCS_PREFIX}/{pq_file.name}"
        logger.info(
            "uploading %s -> gs://%s/%s", pq_file.name, config.GCS_BUCKET, blob_name
        )
        bucket.blob(blob_name).upload_from_filename(str(pq_file))
        uris.append(f"gs://{config.GCS_BUCKET}/{blob_name}")
    return uris


def ensure_dataset(bq: bigquery.Client) -> None:
    """Create the target dataset if it does not exist.

    Args:
        bq: A BigQuery client.
    """
    ds = bigquery.Dataset(f"{PROJECT}.{config.BQ_DATASET}")
    ds.location = config.BQ_LOCATION
    bq.create_dataset(ds, exists_ok=True)
    logger.info(
        "dataset ready: %s.%s (%s)", PROJECT, config.BQ_DATASET, config.BQ_LOCATION
    )


def load(uris: list[str]) -> None:
    """Load Parquet URIs into a partitioned + clustered BigQuery table.

    Args:
        uris: The ``gs://`` Parquet URIs to load.
    """
    bq = bigquery.Client(project=PROJECT)
    ensure_dataset(bq)
    table_id = f"{PROJECT}.{config.BQ_DATASET}.{config.BQ_TABLE}"

    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.PARQUET,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        time_partitioning=bigquery.TimePartitioning(
            type_=bigquery.TimePartitioningType.DAY,
            field=partition_column(),
        ),
        clustering_fields=bq_clustering_columns(),
    )
    logger.info("replacing PoC table %s from %s file(s)", table_id, len(uris))
    bq.load_table_from_uri(uris, table_id, job_config=job_config).result()

    table = bq.get_table(table_id)
    logger.info(
        "Loaded %s rows, %s columns into %s",
        f"{table.num_rows:,}",
        len(table.schema),
        table_id,
    )
    logger.info(
        "partitioned by: %s | clustered by: %s",
        partition_column(),
        ", ".join(bq_clustering_columns()),
    )


def main() -> None:
    """Upload Parquet to GCS and load it into BigQuery."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logger.info("Project: %s", PROJECT)
    load(upload_to_gcs())


if __name__ == "__main__":
    main()
