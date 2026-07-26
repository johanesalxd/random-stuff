#!/usr/bin/env python3
"""Step 0: build a synthetic, date-partitioned kdb+ HDB.

The table mimics a wide, sparse order-book capture. No customer data is used:
every value is randomly generated from the anonymised schema in ``schema.py``.

The customer cannot share sample data (only the DDL and null ratios), so we
recreate the *shape* of the problem - wide, mostly-null, one partition per day,
nanosecond timestamps - and run the real pipeline against it.

Run:
    uv run python 00_generate_synthetic_hdb.py

Knobs (via .env): POC_ROWS, POC_DATES.
"""

from __future__ import annotations

import logging
import time

import config
from kdb_utils import ensure_licensed_pykx, peak_rss_mb
from schema import build_schema

logger = logging.getLogger(__name__)

kx = ensure_licensed_pykx()

SCHEMA = build_schema()
# The partition column (`date`) is VIRTUAL in a kdb+ HDB: it is not physically
# stored, and reappears automatically when a partition is read. So we generate
# every column except `date`.
STORED = [c for c in SCHEMA if c.name != "date"]

# q helper: set null value `nv` at the positions where mask `m` is true.
kx.q("applyNull:{[c;m;nv] @[c;where m;:;nv]}")

_NULLS = {"j": kx.q("0Nj"), "s": kx.q("`"), "p": kx.q("0Np")}
_SYM_POOL = ["AAA", "BBB", "CCC", "DDD", "EEE", "FFF", "GGG", "HHH"]


def _make_column(col, n: int, day: str):
    """Generate one kdb+ column vector of length ``n`` with the right null ratio.

    Args:
        col: The column definition.
        n: Number of rows.
        day: Partition date in kdb+ form (e.g. "2024.01.02").

    Returns:
        A PyKX vector.
    """
    if col.kdb_type == "j":
        base = kx.random.random(n, 1_000_000)
    elif col.kdb_type == "s":
        base = kx.random.random(n, _SYM_POOL)
    elif col.kdb_type == "p":
        base = kx.q(
            "{x + y}",
            kx.q(f"{day}D00:00:00.000000000"),
            kx.random.random(n, kx.q("86400000000000j")),
        )
    else:
        raise ValueError(f"Unsupported kdb_type: {col.kdb_type}")

    if col.null_ratio > 0.0:
        mask = kx.q("{x < y}", kx.random.random(n, 1.0), col.null_ratio)
        base = kx.q("applyNull", base, mask, _NULLS[col.kdb_type])
    return base


def generate_partition(db, day: str, n: int) -> None:
    """Generate and persist one day partition to the HDB.

    Args:
        db: An open ``pykx.DB``.
        day: Partition date in kdb+ form.
        n: Number of rows to generate.
    """
    t0 = time.time()
    data = {col.name: _make_column(col, n, day) for col in STORED}
    tab = kx.Table(data=data)
    db.create(tab, config.BQ_TABLE, kx.q(day), sym_enum="sym", log=False)
    logger.info(
        "partition %s: %s rows x %s cols in %.1fs",
        day,
        f"{n:,}",
        len(STORED),
        time.time() - t0,
    )


def main() -> None:
    """Generate all configured partitions and print a per-partition row count."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logger.info("Generating synthetic HDB at: %s", config.HDB_DIR)
    logger.info(
        "Table: %s | rows/partition: %s | partitions: %s",
        config.BQ_TABLE,
        f"{config.POC_ROWS:,}",
        config.POC_DATES,
    )
    logger.info("Columns: %s (stored: %s, +1 virtual `date`)", len(SCHEMA), len(STORED))

    db = kx.DB(path=str(config.HDB_DIR))
    t0 = time.time()
    for day in config.POC_DATES:
        generate_partition(db, day, config.POC_ROWS)

    logger.info("Done in %.1fs | peak RAM %.0f MB", time.time() - t0, peak_rss_mb())
    db.load(str(config.HDB_DIR), overwrite=True)
    logger.info(
        "Row counts by partition:\n%s",
        str(kx.q(f"select count i by date from {config.BQ_TABLE}")),
    )


if __name__ == "__main__":
    main()
