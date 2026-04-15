"""Unit tests for pipeline.config -- Pydantic model validation and config mapping."""

import pytest
from pydantic import ValidationError

from pipeline.config import (
    ClusterConfig,
    PipelineConfig,
    SourceType,
    _build_pipeline_config,
    _derive_dataset,
    _derive_write_mode,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MINIMAL_CLUSTER_YAML = {
    "source_name": "demo_cluster",
    "source_type": "postgres",
    "source_group": "demo",
    "data_config": {
        "thelook": {
            "tables": {
                "orders": {"etl_mode": "FULL_RELOAD"},
            }
        }
    },
}

_FULL_CLUSTER_YAML = {
    "source_name": "demo_cluster",
    "source_type": "postgres",
    "source_group": "demo",
    "data_config": {
        "thelook": {
            "tables": {
                "users": {
                    "etl_mode": "INCREMENTAL",
                    "backfill_filters": [{"backfill_id": "updated_at"}],
                    "upsert_key": ["id"],
                    "partition_keys": [
                        {"col_name": "created_at", "col_type": "timestamp"}
                    ],
                    "z_order_by": ["status", "gender"],
                },
                "orders": {
                    "etl_mode": "FULL_RELOAD",
                },
                "order_items": {
                    "etl_mode": "INCREMENTAL",
                    "backfill_filters": [{"backfill_id": "created_at"}],
                },
            }
        }
    },
}


def _make_cluster(raw: dict | None = None) -> ClusterConfig:
    return ClusterConfig.model_validate(raw or _MINIMAL_CLUSTER_YAML)


def _make_pipeline_config(
    db_name: str = "thelook",
    tbl_name: str = "orders",
    cluster_raw: dict | None = None,
    project: str = "my-project",
) -> PipelineConfig:
    cluster = _make_cluster(cluster_raw or _FULL_CLUSTER_YAML)
    return _build_pipeline_config(cluster, db_name, tbl_name, project)


# ---------------------------------------------------------------------------
# ClusterConfig validation
# ---------------------------------------------------------------------------


def test_cluster_config_minimal_valid():
    cluster = _make_cluster()
    assert cluster.source_name == "demo_cluster"
    assert cluster.source_type == SourceType.POSTGRES
    assert cluster.source_group == "demo"
    assert "thelook" in cluster.data_config


def test_cluster_config_extra_top_level_fields_ignored():
    """Fields not declared in ClusterConfig (e.g. cron_schedule) are allowed."""
    raw = {
        **_MINIMAL_CLUSTER_YAML,
        "cron_schedule": "0 18 * * *",
        "registra_type": "REPLICATION",
    }
    cluster = ClusterConfig.model_validate(raw)
    assert cluster.source_name == "demo_cluster"


def test_cluster_config_invalid_source_type_raises():
    raw = {**_MINIMAL_CLUSTER_YAML, "source_type": "mysql"}
    with pytest.raises(ValidationError):
        ClusterConfig.model_validate(raw)


def test_cluster_config_full_yaml():
    cluster = _make_cluster(_FULL_CLUSTER_YAML)
    tables = cluster.data_config["thelook"].tables
    assert set(tables) == {"users", "orders", "order_items"}
    assert tables["users"].etl_mode == "INCREMENTAL"
    assert tables["users"].upsert_key == ["id"]
    assert tables["users"].backfill_filters[0].backfill_id == "updated_at"
    assert tables["users"].partition_keys[0].col_name == "created_at"
    assert tables["users"].z_order_by == ["status", "gender"]
    assert tables["orders"].etl_mode == "FULL_RELOAD"
    assert tables["order_items"].etl_mode == "INCREMENTAL"


# ---------------------------------------------------------------------------
# _derive_write_mode
# ---------------------------------------------------------------------------


def test_derive_write_mode_full_reload():
    assert _derive_write_mode("FULL_RELOAD", []) == "overwrite"


def test_derive_write_mode_incremental_with_upsert_key():
    assert _derive_write_mode("INCREMENTAL", ["id"]) == "merge"


def test_derive_write_mode_incremental_without_upsert_key():
    assert _derive_write_mode("INCREMENTAL", []) == "append"


def test_derive_write_mode_unknown_defaults_to_overwrite():
    assert _derive_write_mode("UNKNOWN_MODE", []) == "overwrite"


# ---------------------------------------------------------------------------
# _derive_dataset
# ---------------------------------------------------------------------------


def test_derive_dataset_simple():
    assert _derive_dataset("thelook") == "raw__thelook"


def test_derive_dataset_replaces_hyphens():
    assert _derive_dataset("my-db") == "raw__my_db"


# ---------------------------------------------------------------------------
# _build_pipeline_config: field mapping
# ---------------------------------------------------------------------------


def test_build_pipeline_config_full_reload():
    cfg = _make_pipeline_config(tbl_name="orders")
    assert cfg.source_name == "demo_cluster"
    assert cfg.source_type == SourceType.POSTGRES
    assert cfg.source_group == "demo"
    assert cfg.db_name == "thelook"
    assert cfg.tbl_name == "orders"
    assert cfg.extraction_mode == "full"
    assert cfg.write_mode == "overwrite"
    assert cfg.merge_keys == []
    assert cfg.watermark_column is None
    assert cfg.partition_field is None
    assert cfg.clustering_fields == []


def test_build_pipeline_config_incremental_with_upsert():
    cfg = _make_pipeline_config(tbl_name="users")
    assert cfg.extraction_mode == "incremental"
    assert cfg.write_mode == "merge"
    assert cfg.merge_keys == ["id"]
    assert cfg.watermark_column == "updated_at"
    assert cfg.partition_field == "created_at"
    assert cfg.clustering_fields == ["status", "gender"]


def test_build_pipeline_config_incremental_append_only():
    cfg = _make_pipeline_config(tbl_name="order_items")
    assert cfg.extraction_mode == "incremental"
    assert cfg.write_mode == "append"
    assert cfg.merge_keys == []
    assert cfg.watermark_column == "created_at"


def test_build_pipeline_config_jdbc_secret_convention():
    cfg = _make_pipeline_config(project="my-project")
    assert cfg.jdbc_url_secret == (
        "projects/my-project/secrets/demo_cluster-jdbc-url/versions/latest"
    )


def test_build_pipeline_config_dataset_derived():
    cfg = _make_pipeline_config(db_name="thelook")
    assert cfg.dataset == "raw__thelook"


def test_build_pipeline_config_source_table_convention():
    cfg = _make_pipeline_config(tbl_name="orders")
    assert cfg.source_table == "public.orders"


def test_build_pipeline_config_full_table_id():
    cfg = _make_pipeline_config(
        db_name="thelook", tbl_name="orders", project="my-project"
    )
    assert cfg.full_table_id == "my-project.raw__thelook.orders"


def test_build_pipeline_config_missing_db_raises():
    cluster = _make_cluster(_FULL_CLUSTER_YAML)
    with pytest.raises(KeyError, match="nonexistent"):
        _build_pipeline_config(cluster, "nonexistent", "orders", "my-project")


def test_build_pipeline_config_missing_table_raises():
    cluster = _make_cluster(_FULL_CLUSTER_YAML)
    with pytest.raises(KeyError, match="nonexistent_table"):
        _build_pipeline_config(cluster, "thelook", "nonexistent_table", "my-project")


# ---------------------------------------------------------------------------
# PipelineConfig: merge_keys validation
# ---------------------------------------------------------------------------


def test_pipeline_config_merge_without_keys_raises():
    with pytest.raises(ValidationError, match="merge_keys"):
        PipelineConfig(
            source_name="s",
            source_type=SourceType.POSTGRES,
            source_group="g",
            db_name="db",
            tbl_name="t",
            jdbc_url_secret="projects/p/secrets/s/versions/latest",
            source_table="public.t",
            project="my-project",
            dataset="raw__db",
            table="t",
            write_mode="merge",
            merge_keys=[],  # empty -- should raise
            extraction_mode="incremental",
        )


def test_pipeline_config_merge_with_keys_valid():
    cfg = PipelineConfig(
        source_name="s",
        source_type=SourceType.POSTGRES,
        source_group="g",
        db_name="db",
        tbl_name="t",
        jdbc_url_secret="projects/p/secrets/s/versions/latest",
        source_table="public.t",
        project="my-project",
        dataset="raw__db",
        table="t",
        write_mode="merge",
        merge_keys=["id"],
        extraction_mode="incremental",
    )
    assert cfg.merge_keys == ["id"]


# ---------------------------------------------------------------------------
# Pagination / parallel JDBC
# ---------------------------------------------------------------------------


def test_build_pipeline_config_pagination():
    raw = {
        **_FULL_CLUSTER_YAML,
        "data_config": {
            "thelook": {
                "tables": {
                    "big_table": {
                        "etl_mode": "FULL_RELOAD",
                        "is_paginated": True,
                        "pagination_key": "id",
                        "pagination_size": 20,
                    }
                }
            }
        },
    }
    cluster = ClusterConfig.model_validate(raw)
    cfg = _build_pipeline_config(cluster, "thelook", "big_table", "my-project")
    assert cfg.partition_column == "id"
    assert cfg.num_partitions == 20


def test_build_pipeline_config_no_pagination():
    cfg = _make_pipeline_config(tbl_name="orders")
    assert cfg.partition_column is None
    assert cfg.num_partitions == 10
