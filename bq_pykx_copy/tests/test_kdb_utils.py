"""Tests for the kdb+ -> Arrow conversion logic (no kdb+ runtime required).

These feed in-memory Arrow tables through ``arrow_align`` to document the three
conversion decisions: symbol-null handling, nanosecond INT64 timestamps, and
microsecond ingestion timestamps.
"""

from types import SimpleNamespace

import numpy as np
import pyarrow as pa
import pytest

import kdb_utils
from kdb_utils import (
    arrow_align,
    arrow_schema,
    chunk_ranges,
    peak_rss_mb,
    q_timestamp_raw_to_arrow,
)
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
    assert result.column("inserted_ts").cast(pa.int64()).to_pylist() == [1_000_000]


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


def test_q_timestamp_raw_to_arrow_preserves_nanos_and_nulls():
    """Raw q timestamps receive the Unix epoch offset without losing nulls."""
    raw = np.array([0, 123_456_789, np.iinfo(np.int64).min], dtype=np.int64)

    result = q_timestamp_raw_to_arrow(raw, preserve_nanoseconds=True)

    assert result.to_pylist() == [
        946_684_800_000_000_000,
        946_684_800_123_456_789,
        None,
    ]


def test_q_timestamp_raw_to_arrow_rejects_unsupported_values():
    """Infinity and epoch overflow fail instead of becoming incorrect dates."""
    with pytest.raises(ValueError, match="infinities"):
        q_timestamp_raw_to_arrow(
            np.array([np.iinfo(np.int64).max]), preserve_nanoseconds=True
        )

    overflow = np.iinfo(np.int64).max - kdb_utils._Q_TO_UNIX_EPOCH_NS + 1
    with pytest.raises(ValueError, match="outside"):
        q_timestamp_raw_to_arrow(np.array([overflow]), preserve_nanoseconds=True)


def test_q_timestamp_raw_to_arrow_truncates_to_microseconds():
    """Regular timestamps intentionally truncate sub-microsecond digits."""
    result = q_timestamp_raw_to_arrow(
        np.array([1_999, -1_999]), preserve_nanoseconds=False
    )

    assert result.cast(pa.int64()).to_pylist() == [
        946_684_800_000_001,
        946_684_799_999_999,
    ]


@pytest.mark.parametrize(
    ("platform", "rss", "expected"),
    [("darwin", 10 * 1024**2, 10.0), ("linux", 10 * 1024, 10.0)],
)
def test_peak_rss_mb_handles_platform_units(monkeypatch, platform, rss, expected):
    """Peak RSS accounts for macOS bytes and Linux KiB."""
    monkeypatch.setattr(kdb_utils.sys, "platform", platform)
    monkeypatch.setattr(
        kdb_utils.resource,
        "getrusage",
        lambda _: SimpleNamespace(ru_maxrss=rss),
    )

    assert peak_rss_mb() == expected
