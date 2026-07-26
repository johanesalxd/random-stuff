#!/usr/bin/env python3
"""Step 1: read the HDB one partition at a time and write Parquet in bounded memory.

The customer's pain point: generating one day's JSON file used ~120 GB of RAM in
q. The fix demonstrated here:

    * read each day partition in row-group-sized chunks (using the kdb+ virtual
      `i` index), so the whole partition is never held in memory,
    * convert each chunk to Arrow with correct types and nulls (see kdb_utils),
    * stream it into a Snappy-compressed Parquet file via ParquetWriter.

Result: peak RAM is roughly one chunk, not one day. Parquet is also ~3x smaller
than CSV and self-describing, so BigQuery reads the schema directly.

Run:
    uv run python 01_kdb_to_parquet.py
"""

from __future__ import annotations

import json
import logging
import time

import pyarrow.parquet as pq

import config
from kdb_utils import (
    arrow_schema,
    chunk_ranges,
    chunk_to_arrow,
    ensure_licensed_pykx,
    peak_rss_mb,
)
from schema import build_schema

logger = logging.getLogger(__name__)

kx = ensure_licensed_pykx()

SCHEMA = build_schema()
ARROW_SCHEMA = arrow_schema(SCHEMA)


def convert_partition(day: str) -> dict:
    """Convert one HDB partition to a Parquet file in bounded memory.

    Args:
        day: Partition date in kdb+ form (e.g. "2024.01.02").

    Returns:
        A metrics dict for the partition (rows, seconds, size, peak RSS, path).
    """
    out_path = config.PARQUET_DIR / f"{config.BQ_TABLE}__{day}.parquet"
    tab = config.BQ_TABLE
    n = int(kx.q(f"count select from {tab} where date={day}").py())
    logger.info("Partition %s: %s rows -> %s", day, f"{n:,}", out_path.name)

    chunk = config.PARQUET_ROW_GROUP
    t0 = time.time()
    rows_written = 0

    writer = pq.ParquetWriter(out_path, ARROW_SCHEMA, compression="snappy")
    try:
        for start, end in chunk_ranges(n, chunk):
            qchunk = kx.q(
                f"select from {tab} where date={day}, i within ({start};{end})"
            )
            at = chunk_to_arrow(qchunk, SCHEMA).cast(ARROW_SCHEMA)
            writer.write_table(at, row_group_size=chunk)
            rows_written += at.num_rows
            logger.debug(
                "  chunk %s-%s | peak RAM %.0f MB",
                f"{start:,}",
                f"{end:,}",
                peak_rss_mb(),
            )
    finally:
        writer.close()

    dt = time.time() - t0
    size_mb = out_path.stat().st_size / (1024 * 1024)
    logger.info(
        "  wrote %s rows in %.1fs | %.1f MB | %.1f MB per 1M rows",
        f"{rows_written:,}",
        dt,
        size_mb,
        size_mb / max(rows_written, 1) * 1e6,
    )
    return {
        "date": day,
        "rows": rows_written,
        "seconds": round(dt, 2),
        "parquet_mb": round(size_mb, 2),
        "peak_rss_mb": round(peak_rss_mb(), 1),
        "path": str(out_path),
    }


def main() -> None:
    """Convert all configured partitions and write a metrics summary file."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    db = kx.DB(path=str(config.HDB_DIR))
    db.load(str(config.HDB_DIR), overwrite=True)

    metrics = [convert_partition(day) for day in config.POC_DATES]
    summary = {
        "row_group_size": config.PARQUET_ROW_GROUP,
        "columns": len(SCHEMA),
        "partitions": metrics,
        "peak_rss_mb": round(peak_rss_mb(), 1),
    }
    out = config.DATA_DIR / "metrics_convert.json"
    out.write_text(json.dumps(summary, indent=2))
    logger.info("Metrics -> %s", out)
    logger.info(
        "Overall peak RAM: %.0f MB (vs the customer's ~120 GB JSON dump)",
        summary["peak_rss_mb"],
    )


if __name__ == "__main__":
    main()
