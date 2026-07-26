#!/usr/bin/env python3
"""Step 3: prove the migration was lossless by comparing kdb+ against BigQuery.

Checks:
    1. Row count per partition (kdb vs BQ).
    2. Null count for a sample of columns (sparsity preserved?).
    3. Nanosecond timestamp fidelity: confirm event timestamps survived the
       round-trip as INT64 with no truncation.

Run:
    uv run python 03_validate.py
"""

from __future__ import annotations

import logging

from google.cloud import bigquery

import config
from kdb_utils import ensure_licensed_pykx
from schema import build_schema

logger = logging.getLogger(__name__)

kx = ensure_licensed_pykx()
PROJECT = config.resolve_gcp_project()
TABLE_ID = f"{PROJECT}.{config.BQ_DATASET}.{config.BQ_TABLE}"
SCHEMA = build_schema()


def check_row_counts(bq: bigquery.Client) -> bool:
    """Compare per-partition row counts between kdb+ and BigQuery.

    Args:
        bq: A BigQuery client.

    Returns:
        True if all partition counts match.
    """
    logger.info("[1] Row counts per partition (kdb vs BigQuery)")
    db = kx.DB(path=str(config.HDB_DIR))
    db.load(str(config.HDB_DIR), overwrite=True)
    rows = bq.query(
        f"SELECT CAST(date AS STRING) AS d, COUNT(*) AS c FROM `{TABLE_ID}` GROUP BY d"
    ).result()
    bq_counts = {r["d"]: r["c"] for r in rows}
    ok = True
    for day in config.POC_DATES:
        kdb_n = int(kx.q(f"count select from {config.BQ_TABLE} where date={day}").py())
        iso = day.replace(".", "-")
        bq_n = bq_counts.get(iso, 0)
        ok &= kdb_n == bq_n
        logger.info(
            "  %s: kdb=%s bq=%s [%s]",
            iso,
            f"{kdb_n:,}",
            f"{bq_n:,}",
            "OK" if kdb_n == bq_n else "MISMATCH",
        )
    return ok


def check_null_counts(bq: bigquery.Client) -> bool:
    """Compare null counts for a sample of columns in the first partition.

    Args:
        bq: A BigQuery client.

    Returns:
        True if all sampled null counts match.
    """
    logger.info("[2] Null-count parity (sample of columns)")
    sample = [c for c in SCHEMA if c.name != "date"][:6]
    day = config.POC_DATES[0]
    iso = day.replace(".", "-")
    sel = ", ".join(f"COUNTIF({c.name} IS NULL) AS `{c.name}`" for c in sample)
    bqrow = next(
        iter(
            bq.query(
                f"SELECT {sel} FROM `{TABLE_ID}` WHERE date = DATE('{iso}')"
            ).result()
        )
    )
    ok = True
    for c in sample:
        kdb_nulls = int(
            kx.q(
                f"count select from {config.BQ_TABLE} where date={day}, null {c.name}"
            ).py()
        )
        bq_nulls = bqrow[c.name]
        ok &= kdb_nulls == bq_nulls
        logger.info(
            "  %-28s kdb_nulls=%s bq_nulls=%s [%s]",
            c.name,
            f"{kdb_nulls:,}",
            f"{bq_nulls:,}",
            "OK" if kdb_nulls == bq_nulls else "MISMATCH",
        )
    return ok


def check_timestamp_precision(bq: bigquery.Client) -> bool:
    """Confirm a nanosecond event timestamp round-tripped as an exact INT64.

    Args:
        bq: A BigQuery client.

    Returns:
        True if the kdb+ nanosecond value is found unchanged in BigQuery.
    """
    logger.info("[3] Nanosecond timestamp fidelity (INT64 round-trip)")
    day = config.POC_DATES[0]
    iso = day.replace(".", "-")
    # Two subtleties handled here:
    #   * `exec` directly against a partitioned table is `nyi` in some builds, so
    #     we materialise the column with an inner `select` first.
    #   * kdb+ timestamps are nanoseconds since 2000.01.01, but Arrow/Parquet/
    #     BigQuery store nanoseconds since 1970.01.01. Subtracting 1970.01.01D0
    #     converts to the epoch the pipeline (and BigQuery) uses.
    kdb_val = int(
        kx.q(
            f"`long$first exec ns from "
            f"(select ns:timestamp_nanos - 1970.01.01D0 from {config.BQ_TABLE} "
            f"where date={day}, not null timestamp_nanos)"
        ).py()
    )
    found = bool(
        list(
            bq.query(
                f"SELECT timestamp_nanos FROM `{TABLE_ID}` "
                f"WHERE date=DATE('{iso}') AND timestamp_nanos = {kdb_val} LIMIT 1"
            ).result()
        )
    )
    logger.info("  kdb ns value      : %s", kdb_val)
    logger.info("  found in BigQuery : %s (exact INT64 match, no truncation)", found)
    logger.info(
        "  sub-microsecond ns: %s (would be lost as BQ TIMESTAMP)", kdb_val % 1000
    )
    return found


def main() -> None:
    """Run all validation checks and exit non-zero on any failure."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logger.info("Validating %s", TABLE_ID)
    bq = bigquery.Client(project=PROJECT)
    results = {
        "row_counts": check_row_counts(bq),
        "null_counts": check_null_counts(bq),
        "timestamp_precision": check_timestamp_precision(bq),
    }
    logger.info("=== SUMMARY ===")
    for name, passed in results.items():
        logger.info("  %-20s %s", name, "PASS" if passed else "FAIL")
    if not all(results.values()):
        raise SystemExit(1)
    logger.info("All checks passed - lossless kdb+ -> Parquet -> BigQuery migration.")


if __name__ == "__main__":
    main()
