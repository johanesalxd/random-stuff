"""PyKX and Arrow helpers shared by the pipeline scripts.

The core logic lives in ``arrow_align``, which encodes the three kdb+ -> BigQuery
conversion decisions that matter for this migration:

    1. Nulls: kdb+ numeric nulls (0Nj, 0Nh, ...) already map to Arrow nulls via
       PyKX ``.pa()``. kdb+ SYMBOL nulls arrive as EMPTY strings, so we
       explicitly turn "" back into a real null for STRING columns.
    2. Nanosecond timestamps: kdb+ keeps nanosecond precision. Columns flagged
       ``is_event_ts_nanos`` are stored as INT64 = "nanoseconds since 1970" so
       nothing is lost (mirrors the customer DDL, e.g. ``timestampNanos INT64``).
    3. Ingestion timestamp: plain TIMESTAMP columns are cast to microsecond
       precision, which is what BigQuery's TIMESTAMP type stores.

``arrow_align`` takes a plain ``pyarrow.Table`` so it can be unit-tested without
a running kdb+ instance; ``chunk_to_arrow`` is the thin PyKX wrapper.
"""

from __future__ import annotations

import logging
import resource

import pyarrow as pa
import pyarrow.compute as pc

import config  # noqa: F401  (import for PyKX license side-effects before pykx)
from schema import Column

logger = logging.getLogger(__name__)


def ensure_licensed_pykx():
    """Import PyKX and confirm it is running in licensed (embedded-q) mode.

    Returns:
        The imported ``pykx`` module.

    Raises:
        SystemExit: If PyKX is in unlicensed mode (cannot read a local HDB).
    """
    import pykx as kx

    if not kx.licensed:
        raise SystemExit(
            "PyKX is in UNLICENSED mode - cannot read a local HDB. Provide the "
            "free personal license: drop kc.lic into this folder, or set "
            "KDB_LICENSE_B64 in .env. See README 'Where to paste your license'."
        )
    return kx


def peak_rss_mb() -> float:
    """Return peak resident memory of this process in MB (ru_maxrss is KB)."""
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def chunk_ranges(n: int, chunk: int) -> list[tuple[int, int]]:
    """Split ``n`` rows into inclusive ``(start, end)`` index windows.

    This is the bounded-memory core: it mirrors the kdb+ virtual ``i`` index
    windows used to read one HDB partition a chunk at a time, so the whole
    partition is never materialised in memory at once.

    Args:
        n: Total number of rows in the partition.
        chunk: Maximum rows per window (the Parquet row-group size).

    Returns:
        Inclusive ``[start, end]`` index pairs covering ``0..n-1`` with no gaps
        or overlaps. Empty when ``n <= 0``.

    Raises:
        ValueError: If ``chunk`` is not positive.
    """
    if chunk <= 0:
        raise ValueError("chunk must be positive")
    return [(start, min(start + chunk - 1, n - 1)) for start in range(0, n, chunk)]


def _string_empty_to_null(arr: pa.ChunkedArray | pa.Array):
    """Convert kdb+ symbol nulls (empty strings) back into real Arrow nulls."""
    mask = pc.equal(arr, pa.scalar("", type=pa.string()))
    return pc.if_else(mask, pa.scalar(None, type=pa.string()), arr)


def arrow_align(table: pa.Table, schema: list[Column]) -> pa.Table:
    """Align an Arrow table's columns/types to the target BigQuery schema.

    Args:
        table: Source Arrow table (e.g. from ``PyKX.Table.pa()``) containing all
            columns named in ``schema``.
        schema: Ordered target column definitions.

    Returns:
        A new Arrow table with columns in schema order and BigQuery-compatible
        types, with kdb+ symbol nulls normalised to real nulls and nanosecond
        event timestamps encoded as INT64.
    """
    arrays = []
    names = []
    for col in schema:
        a = table.column(col.name)

        if col.is_event_ts_nanos:
            # Arrow timestamp[ns] -> INT64 nanoseconds since epoch (lossless).
            a = a.cast(pa.int64())
        elif col.bq_type == "TIMESTAMP":
            # safe=False: intentionally truncate ns -> us (BigQuery TIMESTAMP is
            # microsecond). Use is_event_ts_nanos + INT64 to keep full precision.
            a = a.cast(pa.timestamp("us"), safe=False)
        elif col.bq_type == "STRING":
            if not pa.types.is_string(a.type):
                a = a.cast(pa.string())
            a = _string_empty_to_null(a)
        elif col.bq_type == "INT64":
            a = a.cast(pa.int64())
        elif col.bq_type == "DATE":
            a = a.cast(pa.date32())

        arrays.append(a)
        names.append(col.name)

    return pa.table(arrays, names=names)


def chunk_to_arrow(qtab_chunk, schema: list[Column]) -> pa.Table:
    """Convert a PyKX table chunk to a schema-aligned Arrow table.

    Args:
        qtab_chunk: A PyKX table already sliced to a chunk of rows.
        schema: Ordered target column definitions.

    Returns:
        A schema-aligned Arrow table (see ``arrow_align``).
    """
    return arrow_align(qtab_chunk.pa(), schema)


def arrow_schema(schema: list[Column]) -> pa.Schema:
    """Build the target Arrow schema (also the Parquet file schema).

    Args:
        schema: Ordered target column definitions.

    Returns:
        A ``pyarrow.Schema`` with all fields nullable.
    """
    type_map = {
        "INT64": pa.int64(),
        "STRING": pa.string(),
        "DATE": pa.date32(),
        "TIMESTAMP": pa.timestamp("us"),
    }
    fields = [
        pa.field(
            c.name,
            pa.int64() if c.is_event_ts_nanos else type_map[c.bq_type],
            nullable=True,
        )
        for c in schema
    ]
    return pa.schema(fields)
