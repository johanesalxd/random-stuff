"""Unit tests for pipeline.extractors.postgres -- query building logic.

These tests cover the pure Python logic (query construction, watermark
reading) without requiring a live Spark session or Postgres database.
Spark-dependent paths (actual JDBC reads) are integration tests.
"""

import pytest

from pipeline.config import (
    ExtractionConfig,
    ExtractionMode,
    PipelineConfig,
    SourceConfig,
    SourceType,
    TargetConfig,
    WriteMode,
)
from pipeline.extractors.postgres import PostgresExtractor


def _make_config(
    extraction_mode: ExtractionMode = ExtractionMode.FULL,
    watermark_column: str | None = None,
) -> PipelineConfig:
    return PipelineConfig(
        source_name="mydb",
        db_name="public",
        tbl_name="users",
        source=SourceConfig(
            type=SourceType.POSTGRES,
            jdbc_url_secret="projects/p/secrets/s/versions/latest",
            table="public.users",
        ),
        target=TargetConfig(
            project="my-project",
            dataset="raw",
            table="users",
            write_mode=WriteMode.APPEND,
        ),
        extraction=ExtractionConfig(
            mode=extraction_mode,
            watermark_column=watermark_column,
        ),
    )


class TestBuildQuery:
    """Tests for PostgresExtractor._build_query."""

    def test_full_mode_returns_select_star(self):
        extractor = PostgresExtractor()
        config = _make_config(ExtractionMode.FULL)
        # Pass a None spark -- _build_query only calls _read_watermark in
        # incremental mode, so spark is not touched for full mode.
        query = extractor._build_query(spark=None, config=config)  # type: ignore[arg-type]
        assert query == "SELECT * FROM public.users"

    def test_incremental_without_watermark_column_raises(self):
        extractor = PostgresExtractor()
        config = _make_config(ExtractionMode.INCREMENTAL, watermark_column=None)
        with pytest.raises(ValueError, match="watermark_column"):
            extractor._build_query(spark=None, config=config)  # type: ignore[arg-type]

    def test_incremental_first_run_returns_full_query(self, monkeypatch):
        """On first run (no watermark in BQ), falls back to full extraction."""
        extractor = PostgresExtractor()
        config = _make_config(ExtractionMode.INCREMENTAL, watermark_column="updated_at")

        # Simulate no existing watermark (first run)
        monkeypatch.setattr(extractor, "_read_watermark", lambda spark, cfg: None)

        query = extractor._build_query(spark=None, config=config)  # type: ignore[arg-type]
        assert query == "SELECT * FROM public.users"

    def test_incremental_with_watermark_adds_where_clause(self, monkeypatch):
        extractor = PostgresExtractor()
        config = _make_config(ExtractionMode.INCREMENTAL, watermark_column="updated_at")

        monkeypatch.setattr(
            extractor, "_read_watermark", lambda spark, cfg: "2024-01-15 00:00:00"
        )

        query = extractor._build_query(spark=None, config=config)  # type: ignore[arg-type]
        assert "WHERE updated_at > '2024-01-15 00:00:00'" in query
        assert "SELECT * FROM public.users" in query


class TestParallelReadValidation:
    """Tests for partition_column validation in extract()."""

    def test_partition_column_without_bounds_raises(self, monkeypatch):
        """partition_column set but lower/upper bounds missing should raise."""
        from pipeline.config import SourceConfig

        extractor = PostgresExtractor()
        config = _make_config()

        # Inject a source with partition_column but no bounds
        config = config.model_copy(
            update={
                "source": SourceConfig(
                    type=SourceType.POSTGRES,
                    jdbc_url_secret="projects/p/secrets/s/versions/latest",
                    table="public.users",
                    partition_column="id",
                    lower_bound=None,
                    upper_bound=None,
                )
            }
        )

        # Patch resolve_secret and _build_query to isolate the bounds check
        monkeypatch.setattr(
            "pipeline.extractors.postgres.resolve_secret",
            lambda _: "jdbc:postgresql://localhost/test",
        )
        monkeypatch.setattr(
            extractor, "_build_query", lambda spark, cfg: "SELECT * FROM public.users"
        )

        with pytest.raises(ValueError, match="lower_bound and upper_bound"):
            extractor.extract(spark=None, config=config)  # type: ignore[arg-type]
