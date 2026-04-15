"""Unit tests for pipeline.config -- Pydantic model validation and config mapping."""

import pytest
from pydantic import ValidationError

from pipeline.config import (
    ClusterConfig,
    PipelineConfig,
    SourceType,
    _build_blob_path,
    _build_pipeline_config,
    _derive_dataset,
    _derive_write_mode,
    _resolve_etl_mode,
    _resolve_table_names,
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
    gcs_bucket: str = "my-bucket",
) -> PipelineConfig:
    cluster = _make_cluster(cluster_raw or _FULL_CLUSTER_YAML)
    return _build_pipeline_config(cluster, db_name, tbl_name, project, gcs_bucket)


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
# Fix 1: _resolve_etl_mode (optional etl_mode)
# ---------------------------------------------------------------------------


def test_resolve_etl_mode_explicit_full_reload():
    cluster = ClusterConfig.model_validate(
        {
            **_MINIMAL_CLUSTER_YAML,
            "data_config": {"db": {"tables": {"t": {"etl_mode": "FULL_RELOAD"}}}},
        }
    )
    tbl = cluster.data_config["db"].tables["t"]
    assert _resolve_etl_mode(tbl) == "FULL_RELOAD"


def test_resolve_etl_mode_explicit_incremental():
    cluster = ClusterConfig.model_validate(
        {
            **_MINIMAL_CLUSTER_YAML,
            "data_config": {
                "db": {
                    "tables": {
                        "t": {
                            "etl_mode": "INCREMENTAL",
                            "backfill_filters": [{"backfill_id": "updated_at"}],
                        }
                    }
                }
            },
        }
    )
    tbl = cluster.data_config["db"].tables["t"]
    assert _resolve_etl_mode(tbl) == "INCREMENTAL"


def test_resolve_etl_mode_defaults_to_incremental_when_backfill_filters_present():
    """No etl_mode + backfill_filters present -> INCREMENTAL (customer convention)."""
    cluster = ClusterConfig.model_validate(
        {
            **_MINIMAL_CLUSTER_YAML,
            "data_config": {
                "db": {
                    "tables": {
                        "t": {"backfill_filters": [{"backfill_id": "updated_at"}]}
                    }
                }
            },
        }
    )
    tbl = cluster.data_config["db"].tables["t"]
    assert _resolve_etl_mode(tbl) == "INCREMENTAL"


def test_resolve_etl_mode_defaults_to_full_reload_when_no_backfill_filters():
    """No etl_mode + no backfill_filters -> FULL_RELOAD."""
    cluster = ClusterConfig.model_validate(
        {
            **_MINIMAL_CLUSTER_YAML,
            "data_config": {"db": {"tables": {"t": {}}}},
        }
    )
    tbl = cluster.data_config["db"].tables["t"]
    assert _resolve_etl_mode(tbl) == "FULL_RELOAD"


def test_build_pipeline_config_implicit_incremental():
    """Table with backfill_filters but no etl_mode maps correctly end-to-end."""
    raw = {
        **_FULL_CLUSTER_YAML,
        "data_config": {
            "thelook": {
                "tables": {
                    "events": {
                        "backfill_filters": [{"backfill_id": "event_time"}],
                    }
                }
            }
        },
    }
    cfg = _make_pipeline_config(tbl_name="events", cluster_raw=raw)
    assert cfg.extraction_mode == "incremental"
    assert cfg.write_mode == "append"
    assert cfg.watermark_column == "event_time"


def test_build_pipeline_config_implicit_full_reload():
    """Table with neither etl_mode nor backfill_filters defaults to full reload."""
    raw = {
        **_FULL_CLUSTER_YAML,
        "data_config": {"thelook": {"tables": {"lookup": {}}}},
    }
    cfg = _make_pipeline_config(tbl_name="lookup", cluster_raw=raw)
    assert cfg.extraction_mode == "full"
    assert cfg.write_mode == "overwrite"


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
    assert _derive_dataset("thelook") == "raw_thelook"


def test_derive_dataset_replaces_hyphens():
    assert _derive_dataset("my-db") == "raw_my_db"


# ---------------------------------------------------------------------------
# Fix 2: tbl_name_alias + Fix 3: dotted schema.table (_resolve_table_names)
# ---------------------------------------------------------------------------


def test_resolve_table_names_plain_no_alias():
    from pipeline.config import TableConfig

    tbl = TableConfig(etl_mode="FULL_RELOAD")
    source_table, bq_name = _resolve_table_names("users", tbl)
    assert source_table == "public.users"
    assert bq_name == "users"


def test_resolve_table_names_plain_with_alias():
    from pipeline.config import TableConfig

    tbl = TableConfig(etl_mode="FULL_RELOAD", tbl_name_alias="approval_workflows")
    source_table, bq_name = _resolve_table_names("ApprovalWorkflows", tbl)
    assert source_table == "public.ApprovalWorkflows"
    assert bq_name == "approval_workflows"


def test_resolve_table_names_dotted_no_alias():
    from pipeline.config import TableConfig

    tbl = TableConfig(etl_mode="INCREMENTAL")
    source_table, bq_name = _resolve_table_names("saas.tenant_lookups", tbl)
    assert source_table == "saas.tenant_lookups"
    assert bq_name == "saas_tenant_lookups"


def test_resolve_table_names_dotted_with_alias():
    from pipeline.config import TableConfig

    tbl = TableConfig(etl_mode="INCREMENTAL", tbl_name_alias="tenant_lookups")
    source_table, bq_name = _resolve_table_names("saas.tenant_lookups", tbl)
    assert source_table == "saas.tenant_lookups"
    assert bq_name == "tenant_lookups"  # alias wins


def test_build_pipeline_config_tbl_name_alias_overrides_bq_table():
    """tbl_name_alias maps to BQ target table name; JDBC source table is unaffected."""
    raw = {
        **_FULL_CLUSTER_YAML,
        "data_config": {
            "thelook": {
                "tables": {
                    "ApprovalWorkflows": {
                        "etl_mode": "FULL_RELOAD",
                        "tbl_name_alias": "approval_workflows",
                    }
                }
            }
        },
    }
    cfg = _make_pipeline_config(tbl_name="ApprovalWorkflows", cluster_raw=raw)
    assert cfg.table == "approval_workflows"
    assert cfg.source_table == "public.ApprovalWorkflows"


def test_build_pipeline_config_dotted_source_table():
    """schema.table -> source_table as-is, BQ name underscored."""
    raw = {
        **_FULL_CLUSTER_YAML,
        "data_config": {
            "bank-live": {
                "tables": {
                    "saas.tenant_lookups": {
                        "etl_mode": "INCREMENTAL",
                        "backfill_filters": [{"backfill_id": "updated"}],
                    }
                }
            }
        },
    }
    cfg = _make_pipeline_config(
        db_name="bank-live", tbl_name="saas.tenant_lookups", cluster_raw=raw
    )
    assert cfg.source_table == "saas.tenant_lookups"
    assert cfg.table == "saas_tenant_lookups"
    assert cfg.dataset == "raw_bank_live"


# ---------------------------------------------------------------------------
# Fix 5: Quote stripping from table name keys
# ---------------------------------------------------------------------------


def test_build_pipeline_config_quoted_table_name_stripped():
    """YAML keys with surrounding quotes are normalised; caller passes unquoted name."""
    raw = {
        **_FULL_CLUSTER_YAML,
        "data_config": {
            "thelook": {
                "tables": {
                    '"ApprovalWorkflows"': {
                        "etl_mode": "FULL_RELOAD",
                        "tbl_name_alias": "approval_workflows",
                    }
                }
            }
        },
    }
    cfg = _make_pipeline_config(tbl_name="ApprovalWorkflows", cluster_raw=raw)
    assert cfg.table == "approval_workflows"
    assert cfg.tbl_name == "ApprovalWorkflows"


# ---------------------------------------------------------------------------
# Fix 4: _build_blob_path (hierarchical vs flat GCS path)
# ---------------------------------------------------------------------------


def test_build_blob_path_flat():
    assert _build_blob_path("demo_cluster", "configs", None, None) == (
        "configs/demo_cluster.yaml"
    )


def test_build_blob_path_flat_when_only_source_type_given():
    """Both source_type AND source_group must be set for hierarchical path."""
    assert _build_blob_path("demo_cluster", "configs", "postgres", None) == (
        "configs/demo_cluster.yaml"
    )


def test_build_blob_path_flat_when_only_source_group_given():
    assert _build_blob_path("demo_cluster", "configs", None, "prod_postgres") == (
        "configs/demo_cluster.yaml"
    )


def test_build_blob_path_hierarchical():
    path = _build_blob_path(
        "transaction_service_v4_priority",
        "batch_pipeline",
        "postgres",
        "prod_postgres_priority",
    )
    assert path == (
        "batch_pipeline/postgres/prod_postgres_priority"
        "/transaction_service_v4_priority.yaml"
    )


# ---------------------------------------------------------------------------
# Fix 6: gcs_bucket on PipelineConfig
# ---------------------------------------------------------------------------


def test_build_pipeline_config_gcs_bucket_passed_through():
    cfg = _make_pipeline_config(gcs_bucket="my-bucket")
    assert cfg.gcs_bucket == "my-bucket"


# ---------------------------------------------------------------------------
# _build_pipeline_config: core field mapping
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
    assert cfg.dataset == "raw_thelook"


def test_build_pipeline_config_source_table_default_public_schema():
    cfg = _make_pipeline_config(tbl_name="orders")
    assert cfg.source_table == "public.orders"


def test_build_pipeline_config_full_table_id():
    cfg = _make_pipeline_config(
        db_name="thelook", tbl_name="orders", project="my-project"
    )
    assert cfg.full_table_id == "my-project.raw_thelook.orders"


def test_build_pipeline_config_missing_db_raises():
    cluster = _make_cluster(_FULL_CLUSTER_YAML)
    with pytest.raises(KeyError, match="nonexistent"):
        _build_pipeline_config(
            cluster, "nonexistent", "orders", "my-project", "my-bucket"
        )


def test_build_pipeline_config_missing_table_raises():
    cluster = _make_cluster(_FULL_CLUSTER_YAML)
    with pytest.raises(KeyError, match="nonexistent_table"):
        _build_pipeline_config(
            cluster, "thelook", "nonexistent_table", "my-project", "my-bucket"
        )


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
            dataset="raw_db",
            table="t",
            write_mode="merge",
            merge_keys=[],
            extraction_mode="incremental",
            gcs_bucket="my-bucket",
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
        dataset="raw_db",
        table="t",
        write_mode="merge",
        merge_keys=["id"],
        extraction_mode="incremental",
        gcs_bucket="my-bucket",
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
    cfg = _make_pipeline_config(tbl_name="big_table", cluster_raw=raw)
    assert cfg.partition_column == "id"
    assert cfg.num_partitions == 20


def test_build_pipeline_config_no_pagination():
    cfg = _make_pipeline_config(tbl_name="orders")
    assert cfg.partition_column is None
    assert cfg.num_partitions == 10


def test_pagination_size_within_limit_unchanged():
    """Values <= 200 pass through the validator unchanged."""
    from pipeline.config import TableConfig

    tbl = TableConfig(is_paginated=True, pagination_key="id", pagination_size=200)
    assert tbl.pagination_size == 200


def test_pagination_size_capped_at_200(caplog):
    """Values > 200 are capped to 200 and a warning is emitted."""
    import logging

    from pipeline.config import TableConfig

    with caplog.at_level(logging.WARNING, logger="pipeline.config"):
        tbl = TableConfig(
            is_paginated=True, pagination_key="id", pagination_size=1_000_000
        )

    assert tbl.pagination_size == 200
    assert "pagination_size=1000000" in caplog.text
    assert "Capping to 200" in caplog.text


def test_build_pipeline_config_pagination_size_capped_end_to_end():
    """Customer-style million-row pagination_size is capped before numPartitions."""
    raw = {
        **_FULL_CLUSTER_YAML,
        "data_config": {
            "thelook": {
                "tables": {
                    "huge_table": {
                        "etl_mode": "FULL_RELOAD",
                        "is_paginated": True,
                        "pagination_key": "id",
                        "pagination_size": 1_000_000,
                    }
                }
            }
        },
    }
    cfg = _make_pipeline_config(tbl_name="huge_table", cluster_raw=raw)
    assert cfg.num_partitions == 200


# ---------------------------------------------------------------------------
# Customer-style YAML: smoke test with realistic config
# ---------------------------------------------------------------------------


def test_customer_style_yaml_no_etl_mode_with_pagination():
    """Realistic customer table: no etl_mode, backfill_filters, is_paginated,
    schema.table dotted name, extra fields (scheduling, alert) ignored gracefully."""
    raw = {
        "source_name": "transaction_service_v4_priority",
        "source_type": "postgres",
        "source_group": "prod_postgres_priority",
        "cron_schedule": "0 18 * * *",
        "registra_type": "REPLICATION",
        "data_config": {
            "transaction-service-v4": {
                "tables": {
                    "transaction_event": {
                        # etl_mode intentionally omitted -- customer convention
                        "backfill_filters": [{"backfill_id": "created"}],
                        "partition_keys": [
                            {
                                "order": 1,
                                "col_name": "created",
                                "col_type": "timestamp",
                                "col_alias": "dt",
                                "col_cast_method": "general.datetime_to_date",
                            }
                        ],
                        "z_order_by": ["transaction_id"],
                        "is_paginated": True,
                        "pagination_key": "id",
                        "scheduling": {
                            "autoscale": {"min_workers": 1, "max_workers": 4}
                        },
                        "alert": {"airflow": [{"channel": "recon-auto-alert"}]},
                    }
                }
            }
        },
    }
    cfg = _make_pipeline_config(
        db_name="transaction-service-v4",
        tbl_name="transaction_event",
        cluster_raw=raw,
    )
    assert cfg.extraction_mode == "incremental"
    assert cfg.write_mode == "append"  # no upsert_key
    assert cfg.watermark_column == "created"
    assert cfg.partition_field == "created"
    assert cfg.clustering_fields == ["transaction_id"]
    assert cfg.partition_column == "id"
    assert cfg.dataset == "raw_transaction_service_v4"
    assert cfg.source_table == "public.transaction_event"
    # Unknown fields land in extra without raising
    assert "scheduling" in cfg.extra
    assert "alert" in cfg.extra
