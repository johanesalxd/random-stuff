"""Unit tests for pipeline.extractors.postgres -- query building logic.

These tests cover the pure Python logic (query construction, watermark
reading) without requiring a live Spark session or Postgres database.
Spark-dependent paths (actual JDBC reads) are integration tests.
"""

import pytest

from pipeline.config import PipelineConfig, SourceType
from pipeline.extractors.postgres import PostgresExtractor


def _make_config(
    extraction_mode: str = "full",
    watermark_column: str | None = None,
    partition_column: str | None = None,
    num_partitions: int = 10,
) -> PipelineConfig:
    return PipelineConfig(
        source_name="demo_cluster",
        source_type=SourceType.POSTGRES,
        source_group="demo",
        db_name="thelook",
        tbl_name="users",
        jdbc_url_secret="projects/p/secrets/demo_cluster-jdbc-url/versions/latest",
        source_table="public.users",
        partition_column=partition_column,
        num_partitions=num_partitions,
        project="my-project",
        dataset="raw_thelook",
        table="users",
        write_mode="append",
        extraction_mode=extraction_mode,
        watermark_column=watermark_column,
        gcs_bucket="my-bucket",
    )


class TestBuildQuery:
    """Tests for PostgresExtractor._build_query."""

    def test_full_mode_returns_select_star(self):
        extractor = PostgresExtractor()
        config = _make_config("full")
        # Pass a None spark -- _build_query only calls _read_watermark in
        # incremental mode, so spark is not touched for full mode.
        query = extractor._build_query(spark=None, config=config)  # type: ignore[arg-type]
        assert query == "SELECT * FROM public.users"

    def test_incremental_without_watermark_column_raises(self):
        extractor = PostgresExtractor()
        config = _make_config("incremental", watermark_column=None)
        with pytest.raises(ValueError, match="watermark_column"):
            extractor._build_query(spark=None, config=config)  # type: ignore[arg-type]

    def test_incremental_first_run_returns_full_query(self, monkeypatch):
        """On first run (no watermark in BQ), falls back to full extraction."""
        extractor = PostgresExtractor()
        config = _make_config("incremental", watermark_column="updated_at")

        # Simulate no existing watermark (first run)
        monkeypatch.setattr(extractor, "_read_watermark", lambda spark, cfg: None)

        query = extractor._build_query(spark=None, config=config)  # type: ignore[arg-type]
        assert query == "SELECT * FROM public.users"

    def test_incremental_with_watermark_adds_where_clause(self, monkeypatch):
        extractor = PostgresExtractor()
        config = _make_config("incremental", watermark_column="updated_at")

        monkeypatch.setattr(
            extractor, "_read_watermark", lambda spark, cfg: "2024-01-15 00:00:00"
        )

        query = extractor._build_query(spark=None, config=config)  # type: ignore[arg-type]
        assert "WHERE updated_at > '2024-01-15 00:00:00'" in query
        assert "SELECT * FROM public.users" in query


class TestParallelRead:
    """Tests for partition_column parallel read path in extract()."""

    def test_partition_column_uses_num_partitions(self, monkeypatch):
        """When partition_column is set, numPartitions is passed to JDBC options."""
        extractor = PostgresExtractor()
        config = _make_config(partition_column="id", num_partitions=20)

        captured_options: dict = {}

        def fake_resolve_secret(_):
            return "jdbc:postgresql://localhost/test"

        def fake_build_query(spark, cfg):
            return "SELECT * FROM public.users"

        monkeypatch.setattr(
            "pipeline.extractors.postgres.resolve_secret", fake_resolve_secret
        )
        monkeypatch.setattr(extractor, "_build_query", fake_build_query)

        class FakeLoader:
            def load(self):
                return "dataframe"

        class FakeFormat:
            def options(self, **kwargs):
                captured_options.update(kwargs)
                return FakeLoader()

        class FakeRead:
            def format(self, _):
                return FakeFormat()

        class FakeSpark:
            read = FakeRead()

        extractor.extract(spark=FakeSpark(), config=config)  # type: ignore[arg-type]

        assert captured_options.get("partitionColumn") == "id"
        assert captured_options.get("numPartitions") == "20"

    def test_no_partition_column_omits_jdbc_partition_options(self, monkeypatch):
        """Without partition_column, no JDBC partition keys are passed."""
        extractor = PostgresExtractor()
        config = _make_config()

        captured_options: dict = {}

        monkeypatch.setattr(
            "pipeline.extractors.postgres.resolve_secret",
            lambda _: "jdbc:postgresql://localhost/test",
        )
        monkeypatch.setattr(
            extractor, "_build_query", lambda spark, cfg: "SELECT * FROM public.users"
        )

        class FakeLoader:
            def load(self):
                return "dataframe"

        class FakeFormat:
            def options(self, **kwargs):
                captured_options.update(kwargs)
                return FakeLoader()

        class FakeRead:
            def format(self, _):
                return FakeFormat()

        class FakeSpark:
            read = FakeRead()

        extractor.extract(spark=FakeSpark(), config=config)  # type: ignore[arg-type]

        assert "partitionColumn" not in captured_options
        assert "numPartitions" not in captured_options
