"""Tests for the kdb+ -> Arrow conversion logic (no kdb+ runtime required).

These feed in-memory Arrow tables through ``arrow_align`` to document the three
conversion decisions: symbol-null handling, nanosecond INT64 timestamps, and
microsecond ingestion timestamps.
"""

import pyarrow as pa
import pytest

from kdb_utils import arrow_align, arrow_schema, chunk_ranges
from schema import Column


def test_arrow_align_symbol_empty_becomes_null():
    """kdb+ symbol nulls arrive as empty strings and must become real nulls."""
    schema = [Column("sym", "s", "STRING", 0.0)]
    table = pa.table({"sym": pa.array(["AAA", "", "BBB"], type=pa.string())})

    result = arrow_align(table, schema)

    assert result.column("sym").to_pylist() == ["AAA", None, "BBB"]


def test_arrow_align_event_timestamp_becomes_int64_nanos():
    """Event timestamps are stored as INT64 nanoseconds-since-epoch, losslessly."""
    schema = [Column("ts", "p", "INT64", 0.0, is_event_ts_nanos=True)]
    # 1 second + 123456789 ns after epoch; the sub-microsecond digits must survive.
    ns_value = 1_000_000_000 + 123_456_789
    table = pa.table({"ts": pa.array([ns_value], type=pa.timestamp("ns"))})

    result = arrow_align(table, schema)

    assert result.schema.field("ts").type == pa.int64()
    assert result.column("ts").to_pylist() == [ns_value]


def test_arrow_align_ingestion_timestamp_is_microsecond():
    """Plain TIMESTAMP columns are normalised to microsecond precision."""
    schema = [Column("inserted_ts", "p", "TIMESTAMP", 0.0)]
    table = pa.table(
        {"inserted_ts": pa.array([1_000_000_123], type=pa.timestamp("ns"))}
    )

    result = arrow_align(table, schema)

    assert result.schema.field("inserted_ts").type == pa.timestamp("us")


def test_arrow_align_preserves_numeric_nulls_and_order():
    """Numeric nulls pass through and columns come back in schema order."""
    schema = [
        Column("b", "j", "INT64", 0.0),
        Column("a", "j", "INT64", 0.0),
    ]
    table = pa.table({"a": pa.array([1, None]), "b": pa.array([None, 2])})

    result = arrow_align(table, schema)

    assert result.column_names == ["b", "a"]
    assert result.column("b").to_pylist() == [None, 2]
    assert result.column("a").to_pylist() == [1, None]


def test_arrow_schema_marks_event_ts_as_int64():
    """The Parquet schema encodes event timestamps as nullable INT64."""
    schema = [
        Column("date", "d", "DATE", 0.0),
        Column("ts", "p", "INT64", 0.0, is_event_ts_nanos=True),
        Column("inserted_ts", "p", "TIMESTAMP", 0.0),
    ]

    result = arrow_schema(schema)

    assert result.field("date").type == pa.date32()
    assert result.field("ts").type == pa.int64()
    assert result.field("inserted_ts").type == pa.timestamp("us")
    assert all(result.field(f).nullable for f in result.names)


def test_chunk_ranges_exact_multiple():
    """When rows divide evenly, windows are full and non-overlapping."""
    assert chunk_ranges(10, 5) == [(0, 4), (5, 9)]


def test_chunk_ranges_clamps_final_window():
    """A partial final window ends at n-1, never past the real row count."""
    assert chunk_ranges(7, 3) == [(0, 2), (3, 5), (6, 6)]
    # Mirrors the PoC default: 400k rows at a 250k row group.
    assert chunk_ranges(400_000, 250_000) == [(0, 249_999), (250_000, 399_999)]


def test_chunk_ranges_covers_every_row_contiguously():
    """The windows must tile 0..n-1 exactly: no gaps, no overlaps, full cover."""
    n, chunk = 1_000_003, 250_000
    ranges = chunk_ranges(n, chunk)

    assert ranges[0][0] == 0
    assert ranges[-1][1] == n - 1
    for (_, prev_end), (next_start, _) in zip(ranges, ranges[1:], strict=False):
        assert next_start == prev_end + 1
    assert sum(end - start + 1 for start, end in ranges) == n


def test_chunk_ranges_empty_partition():
    """An empty partition yields no windows."""
    assert chunk_ranges(0, 250_000) == []


def test_chunk_ranges_rejects_non_positive_chunk():
    """A non-positive chunk size is a programming error, not a silent no-op."""
    with pytest.raises(ValueError):
        chunk_ranges(100, 0)
