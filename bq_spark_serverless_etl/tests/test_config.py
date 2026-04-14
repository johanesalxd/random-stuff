"""Unit tests for pipeline.config -- Pydantic model validation."""

import pytest
from pydantic import ValidationError

from pipeline.config import (
    ExtractionConfig,
    ExtractionMode,
    PipelineConfig,
    SourceConfig,
    SourceType,
    TargetConfig,
    WriteMode,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _postgres_source(**overrides) -> dict:
    return {
        "type": "postgres",
        "jdbc_url_secret": "projects/p/secrets/s/versions/latest",
        "table": "public.users",
        **overrides,
    }


def _target(**overrides) -> dict:
    return {
        "project": "my-project",
        "dataset": "raw",
        "table": "users",
        **overrides,
    }


def _make_config(source: dict, target: dict, extraction: dict | None = None) -> dict:
    raw = {"source": source, "target": target}
    if extraction:
        raw["extraction"] = extraction
    return raw


# ---------------------------------------------------------------------------
# SourceConfig
# ---------------------------------------------------------------------------


def test_postgres_source_valid():
    src = SourceConfig.model_validate(_postgres_source())
    assert src.type == SourceType.POSTGRES
    assert src.fetch_size == 10000  # default


def test_postgres_source_missing_jdbc_url_raises():
    with pytest.raises(ValidationError, match="Postgres source requires"):
        SourceConfig.model_validate({"type": "postgres", "table": "public.users"})


def test_postgres_source_missing_table_raises():
    with pytest.raises(ValidationError, match="Postgres source requires"):
        SourceConfig.model_validate(
            {
                "type": "postgres",
                "jdbc_url_secret": "projects/p/secrets/s/versions/latest",
            }
        )


# ---------------------------------------------------------------------------
# TargetConfig
# ---------------------------------------------------------------------------


def test_target_valid_defaults():
    tgt = TargetConfig.model_validate(_target())
    assert tgt.write_mode == WriteMode.OVERWRITE
    assert tgt.merge_keys == []
    assert tgt.clustering_fields == []


def test_target_full_table_id():
    tgt = TargetConfig.model_validate(_target())
    assert tgt.full_table_id == "my-project.raw.users"


def test_target_merge_without_keys_raises():
    with pytest.raises(ValidationError, match="merge_keys"):
        TargetConfig.model_validate(_target(write_mode="merge"))


def test_target_merge_with_keys_valid():
    tgt = TargetConfig.model_validate(_target(write_mode="merge", merge_keys=["id"]))
    assert tgt.write_mode == WriteMode.MERGE
    assert tgt.merge_keys == ["id"]


# ---------------------------------------------------------------------------
# ExtractionConfig
# ---------------------------------------------------------------------------


def test_extraction_defaults():
    ext = ExtractionConfig()
    assert ext.mode == ExtractionMode.FULL
    assert ext.watermark_column is None


# ---------------------------------------------------------------------------
# PipelineConfig
# ---------------------------------------------------------------------------


def test_pipeline_config_valid_postgres():
    raw = _make_config(source=_postgres_source(), target=_target())
    cfg = PipelineConfig.model_validate(
        {**raw, "source_name": "mydb", "db_name": "public", "tbl_name": "users"}
    )
    assert cfg.source.type == SourceType.POSTGRES
    assert cfg.target.full_table_id == "my-project.raw.users"
    assert cfg.extraction.mode == ExtractionMode.FULL


def test_pipeline_config_incremental_propagates():
    raw = _make_config(
        source=_postgres_source(),
        target=_target(write_mode="append"),
        extraction={"mode": "incremental", "watermark_column": "updated_at"},
    )
    cfg = PipelineConfig.model_validate(
        {**raw, "source_name": "s", "db_name": "d", "tbl_name": "t"}
    )
    assert cfg.extraction.mode == ExtractionMode.INCREMENTAL
    assert cfg.extraction.watermark_column == "updated_at"
