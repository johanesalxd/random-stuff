"""Tests for the anonymised schema definition."""

from schema import bq_clustering_columns, build_schema, partition_column


def test_build_schema_is_wide_and_sparse():
    """The table reproduces the real-world wide/sparse shape (428 columns)."""
    schema = build_schema()

    assert len(schema) > 400
    # Most columns should be predominantly null (sparse capture).
    sparse = [c for c in schema if c.null_ratio >= 0.7]
    assert len(sparse) > len(schema) / 2


def test_build_schema_has_unique_column_names():
    """Duplicate column names would break the Parquet/BigQuery load."""
    names = [c.name for c in build_schema()]

    assert len(names) == len(set(names))


def test_partition_and_clustering_columns_exist():
    """Partition and clustering columns must be real columns in the schema."""
    names = {c.name for c in build_schema()}

    assert partition_column() in names
    assert set(bq_clustering_columns()).issubset(names)
    assert len(bq_clustering_columns()) <= 4  # BigQuery clustering limit


def test_event_timestamps_map_to_int64():
    """Nanosecond event timestamps must target INT64 to preserve precision."""
    event_ts = [c for c in build_schema() if c.is_event_ts_nanos]

    assert event_ts  # there is at least one
    assert all(c.bq_type == "INT64" for c in event_ts)
