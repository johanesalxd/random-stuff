"""Pipeline configuration: YAML schema (Pydantic) and GCS loader.

Config files use a hierarchical, cluster-level format. One YAML file covers
an entire source cluster (all databases and tables). Two GCS path conventions
are supported:

  Flat (simple):
    gs://<bucket>/<configs_prefix>/<source_name>.yaml

  Hierarchical (mirrors customer layout):
    gs://<bucket>/<configs_prefix>/<source_type>/<source_group>/<source_name>.yaml

The hierarchical path is used when --source_type and --source_group are
provided; otherwise the flat path is used.

The pipeline is invoked once per table; source_name, db_name, and tbl_name
are passed as CLI/procedure arguments and used to select the correct table
entry from the YAML.

Secrets (JDBC URLs) are resolved by convention from Secret Manager:
  projects/<project>/secrets/<source_name>-jdbc-url/versions/latest

Never store credentials inline in config files.
"""

import logging
from enum import Enum
from typing import Any

import yaml
from google.cloud import secretmanager, storage
from pydantic import BaseModel, Field, field_validator, model_validator

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SourceType(str, Enum):
    """Supported pipeline source types.

    Add new entries here when registering a new extractor.
    """

    POSTGRES = "postgres"
    # MYSQL = "mysql"          # future
    # COCKROACHDB = "cockroachdb"  # future


# ---------------------------------------------------------------------------
# Cluster YAML models  (hierarchical, customer-style)
# ---------------------------------------------------------------------------


class BackfillFilter(BaseModel):
    """Describes the watermark column used for incremental extraction."""

    backfill_id: str = Field(description="Column name used as the high-watermark.")

    model_config = {"extra": "allow"}


class PartitionKey(BaseModel):
    """Describes a BigQuery partition column."""

    col_name: str = Field(description="Column to partition by.")
    col_type: str = Field(description="Column data type (e.g. timestamp, date).")

    model_config = {"extra": "allow"}


class TableConfig(BaseModel):
    """Per-table configuration entry inside data_config.

    etl_mode is optional. When omitted:
      - INCREMENTAL is assumed when backfill_filters are present.
      - FULL_RELOAD is assumed when backfill_filters are absent.

    This matches the customer convention where most tables are implicitly
    incremental and only specify FULL_RELOAD explicitly.
    """

    etl_mode: str | None = Field(
        default=None,
        description=(
            "ETL strategy: FULL_RELOAD or INCREMENTAL. "
            "Inferred from backfill_filters when omitted."
        ),
    )
    backfill_filters: list[BackfillFilter] = Field(
        default_factory=list,
        description=(
            "Watermark columns for incremental extraction. "
            "Only the first entry is used."
        ),
    )
    upsert_key: list[str] = Field(
        default_factory=list,
        description="Columns that uniquely identify a row for upsert.",
    )
    partition_keys: list[PartitionKey] = Field(
        default_factory=list,
        description="BigQuery partition columns. Only the first entry is used.",
    )
    z_order_by: list[str] = Field(
        default_factory=list,
        description="Columns for BigQuery clustering (analogous to Z-order).",
    )
    is_paginated: bool = Field(
        default=False,
        description="Enable parallel JDBC reads via a pagination key.",
    )
    pagination_key: str | None = Field(
        default=None,
        description="Column used for parallel JDBC partitioning.",
    )
    pagination_size: int = Field(
        default=10,
        description=(
            "Number of JDBC partitions (numPartitions) for parallel reads. "
            "This is a Spark JDBC partition count — NOT a row batch size. "
            "Keep <= 200; values above that are capped with a warning to "
            "prevent spawning excessive parallel JDBC connections."
        ),
    )

    @field_validator("pagination_size", mode="after")
    @classmethod
    def _cap_pagination_size(cls, v: int) -> int:
        """Cap pagination_size to prevent excessive JDBC connections.

        Customer configs often set this field as a row-count (e.g. 1_000_000)
        rather than a partition count. Passing 1 million as numPartitions to
        Spark JDBC would spawn one million parallel connections, which is
        catastrophic. Cap at 200 and warn so the pipeline stays safe even
        when the caller misuses the field.
        """
        _MAX_PARTITIONS = 200
        if v > _MAX_PARTITIONS:
            logger.warning(
                "pagination_size=%d exceeds the maximum safe partition count (%d). "
                "This field is the JDBC numPartitions value, not a row count. "
                "Capping to %d to prevent excessive parallel connections.",
                v,
                _MAX_PARTITIONS,
                _MAX_PARTITIONS,
            )
            return _MAX_PARTITIONS
        return v

    tbl_name_alias: str | None = Field(
        default=None,
        description=(
            "Override for the BigQuery target table name. "
            "When set, the BQ table will be named by this value instead of tbl_name."
        ),
    )

    model_config = {"extra": "allow"}


class DatabaseConfig(BaseModel):
    """Per-database section inside data_config."""

    tables: dict[str, TableConfig] = Field(default_factory=dict)

    model_config = {"extra": "allow"}


class ClusterConfig(BaseModel):
    """Root cluster-level YAML schema.

    One file per source cluster, containing configuration for all
    databases and tables served by that cluster.
    """

    source_name: str = Field(description="Logical identifier for the source cluster.")
    source_type: SourceType = Field(description="Source database technology.")
    source_group: str = Field(description="Organisational grouping for the source.")
    data_config: dict[str, DatabaseConfig] = Field(
        default_factory=dict,
        description="Nested mapping of database_name -> DatabaseConfig.",
    )

    model_config = {"extra": "allow"}


# ---------------------------------------------------------------------------
# Flat runtime model
# ---------------------------------------------------------------------------


class PipelineConfig(BaseModel):
    """Flat runtime configuration for a single pipeline invocation.

    Derived from ClusterConfig by resolving the specific db_name / tbl_name
    requested for this run. All consumers (extractors, writers) use this model
    directly -- no nested sub-models.
    """

    # Identity
    source_name: str
    source_type: SourceType
    source_group: str
    db_name: str
    tbl_name: str

    # Source
    jdbc_url_secret: str = Field(
        description=(
            "GCP Secret Manager resource name for the JDBC URL. "
            "Derived by convention: "
            "projects/<project>/secrets/<source_name>-jdbc-url/versions/latest"
        )
    )
    source_table: str = Field(
        description=(
            "Fully qualified source table for JDBC reads. "
            "If tbl_name contains a dot (schema.table), used as-is. "
            "Otherwise defaults to public.<tbl_name>."
        )
    )
    partition_column: str | None = Field(
        default=None,
        description="Column used to parallelise JDBC reads via numPartitions.",
    )
    num_partitions: int = Field(default=10)
    fetch_size: int = Field(default=10000)

    # Target
    project: str = Field(description="GCP project ID for target BigQuery dataset.")
    dataset: str = Field(
        description=(
            "BigQuery dataset name. Derived by convention: raw_{db_name} "
            "with hyphens replaced by underscores."
        )
    )
    table: str = Field(
        description=(
            "BigQuery table name. Equals tbl_name_alias if set, otherwise "
            "tbl_name (with dots replaced by underscores for dotted names)."
        )
    )
    write_mode: str = Field(
        description="Write strategy: overwrite | append | merge.",
    )
    merge_keys: list[str] = Field(default_factory=list)
    partition_field: str | None = Field(default=None)
    clustering_fields: list[str] = Field(default_factory=list)

    # Extraction
    extraction_mode: str = Field(
        description="Extraction strategy: full | incremental.",
    )
    watermark_column: str | None = Field(default=None)

    # Infrastructure
    gcs_bucket: str = Field(
        description=(
            "GCS bucket used for pipeline configs and BigQuery indirect write "
            "staging (temporaryGcsBucket). Reuses the config bucket so no "
            "additional infrastructure is needed."
        )
    )

    # Pass-through fields from the YAML that the pipeline does not act on
    extra: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_merge_keys(self) -> "PipelineConfig":
        if self.write_mode == "merge" and not self.merge_keys:
            raise ValueError("write_mode=merge requires merge_keys to be non-empty.")
        return self

    @property
    def full_table_id(self) -> str:
        """Return project.dataset.table format."""
        return f"{self.project}.{self.dataset}.{self.table}"


# ---------------------------------------------------------------------------
# Config mapping helpers
# ---------------------------------------------------------------------------

_ETL_MODE_TO_EXTRACTION = {
    "FULL_RELOAD": "full",
    "INCREMENTAL": "incremental",
}


def _resolve_etl_mode(tbl_cfg: TableConfig) -> str:
    """Resolve the effective ETL mode for a table.

    When etl_mode is explicitly set, that value is used directly.
    When omitted, the mode is inferred:
      - INCREMENTAL if backfill_filters are present (customer convention)
      - FULL_RELOAD otherwise

    Args:
        tbl_cfg: Parsed table configuration entry.

    Returns:
        Resolved ETL mode string: "FULL_RELOAD" or "INCREMENTAL".
    """
    if tbl_cfg.etl_mode is not None:
        return tbl_cfg.etl_mode
    return "INCREMENTAL" if tbl_cfg.backfill_filters else "FULL_RELOAD"


def _derive_write_mode(etl_mode: str, upsert_key: list[str]) -> str:
    """Derive the write mode from the etl_mode and presence of upsert_key.

    Args:
        etl_mode: Resolved ETL mode string.
        upsert_key: List of merge key columns.

    Returns:
        One of "overwrite", "append", or "merge".
    """
    if etl_mode == "FULL_RELOAD":
        return "overwrite"
    if etl_mode == "INCREMENTAL":
        return "merge" if upsert_key else "append"
    # Unknown etl_mode -- fall back to overwrite (safe default)
    logger.warning("Unknown etl_mode '%s' -- defaulting to overwrite.", etl_mode)
    return "overwrite"


def _derive_dataset(db_name: str) -> str:
    """Derive the BigQuery dataset name from the database name.

    Convention: raw_{db_name} with hyphens replaced by underscores.

    Args:
        db_name: Source database or schema name.

    Returns:
        BigQuery dataset name.
    """
    return f"raw_{db_name.replace('-', '_')}"


def _resolve_table_names(tbl_name: str, tbl_cfg: TableConfig) -> tuple[str, str]:
    """Resolve source_table (JDBC) and BQ target table name.

    Handles three cases:
      1. Dotted name (schema.table): JDBC uses it as-is; BQ name is
         schema_table (underscored), unless tbl_name_alias overrides.
      2. Plain name: JDBC prepends 'public.'; BQ name equals tbl_name,
         unless tbl_name_alias overrides.
      3. tbl_name_alias always wins for the BQ side.

    Args:
        tbl_name: The (already quote-stripped) table key from the YAML.
        tbl_cfg: Parsed table configuration entry.

    Returns:
        Tuple of (source_table, bq_table_name).
    """
    if "." in tbl_name:
        source_table = tbl_name
        schema_part, table_part = tbl_name.split(".", 1)
        default_bq_name = f"{schema_part}_{table_part}"
    else:
        source_table = f"public.{tbl_name}"
        default_bq_name = tbl_name

    bq_table_name = tbl_cfg.tbl_name_alias or default_bq_name
    return source_table, bq_table_name


def _build_pipeline_config(
    cluster: ClusterConfig,
    db_name: str,
    tbl_name: str,
    project: str,
    gcs_bucket: str,
) -> "PipelineConfig":
    """Build a flat PipelineConfig from a ClusterConfig for one table.

    Table name lookup normalises surrounding quotes from the YAML key
    (e.g. '"ApprovalWorkflows"' -> 'ApprovalWorkflows') so the caller
    never needs to quote the tbl_name argument.

    Args:
        cluster: Parsed cluster-level YAML config.
        db_name: Database or schema name to look up.
        tbl_name: Table name to look up (quotes are stripped automatically).
        project: GCP project ID (used for secret name and BQ target).
        gcs_bucket: GCS bucket for configs and BQ indirect write staging.

    Returns:
        Flat PipelineConfig ready for use by extractors and writers.

    Raises:
        KeyError: If db_name or tbl_name is not found in the cluster config.
    """
    if db_name not in cluster.data_config:
        raise KeyError(
            f"Database '{db_name}' not found in cluster config for "
            f"source '{cluster.source_name}'. "
            f"Available: {sorted(cluster.data_config)}"
        )
    db_cfg = cluster.data_config[db_name]

    # Normalise table keys: strip surrounding quotes that YAML preserves
    # (e.g. '"ApprovalWorkflows"' -> 'ApprovalWorkflows')
    normalized_tables = {k.strip("\"'"): v for k, v in db_cfg.tables.items()}
    clean_tbl_name = tbl_name.strip("\"'")

    if clean_tbl_name not in normalized_tables:
        raise KeyError(
            f"Table '{clean_tbl_name}' not found under db '{db_name}' in cluster "
            f"config for source '{cluster.source_name}'. "
            f"Available: {sorted(normalized_tables)}"
        )
    tbl_cfg = normalized_tables[clean_tbl_name]

    etl_mode = _resolve_etl_mode(tbl_cfg)
    upsert_key = tbl_cfg.upsert_key

    extraction_mode = _ETL_MODE_TO_EXTRACTION.get(etl_mode, "full")
    write_mode = _derive_write_mode(etl_mode, upsert_key)
    watermark_column = (
        tbl_cfg.backfill_filters[0].backfill_id if tbl_cfg.backfill_filters else None
    )
    partition_field = (
        tbl_cfg.partition_keys[0].col_name if tbl_cfg.partition_keys else None
    )
    partition_column = tbl_cfg.pagination_key if tbl_cfg.is_paginated else None
    num_partitions = tbl_cfg.pagination_size if tbl_cfg.is_paginated else 10

    jdbc_url_secret = (
        f"projects/{project}/secrets/{cluster.source_name}-jdbc-url/versions/latest"
    )

    source_table, bq_table_name = _resolve_table_names(clean_tbl_name, tbl_cfg)

    # Fields that are explicitly modelled and mapped -- exclude from extra
    known_fields = {
        "etl_mode",
        "backfill_filters",
        "upsert_key",
        "partition_keys",
        "z_order_by",
        "is_paginated",
        "pagination_key",
        "pagination_size",
        "tbl_name_alias",
    }
    extra = {k: v for k, v in tbl_cfg.model_extra.items() if k not in known_fields}

    return PipelineConfig(
        source_name=cluster.source_name,
        source_type=cluster.source_type,
        source_group=cluster.source_group,
        db_name=db_name,
        tbl_name=clean_tbl_name,
        jdbc_url_secret=jdbc_url_secret,
        source_table=source_table,
        partition_column=partition_column,
        num_partitions=num_partitions,
        project=project,
        dataset=_derive_dataset(db_name),
        table=bq_table_name,
        write_mode=write_mode,
        merge_keys=upsert_key,
        partition_field=partition_field,
        clustering_fields=tbl_cfg.z_order_by,
        extraction_mode=extraction_mode,
        watermark_column=watermark_column,
        gcs_bucket=gcs_bucket,
        extra=extra,
    )


# ---------------------------------------------------------------------------
# GCS loader
# ---------------------------------------------------------------------------


def _read_gcs_yaml(bucket_name: str, blob_path: str) -> dict:
    """Download and parse a YAML file from GCS."""
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_path)
    content = blob.download_as_text()
    return yaml.safe_load(content)


def _build_blob_path(
    source_name: str,
    configs_prefix: str,
    source_type: str | None,
    source_group: str | None,
) -> str:
    """Construct the GCS blob path for a cluster config file.

    When source_type and source_group are both provided, uses the
    hierarchical layout that mirrors the customer's repo structure:
      <configs_prefix>/<source_type>/<source_group>/<source_name>.yaml

    Otherwise falls back to the flat layout:
      <configs_prefix>/<source_name>.yaml

    Args:
        source_name: Source cluster name.
        configs_prefix: Top-level prefix inside the bucket.
        source_type: Optional source type (e.g. "postgres").
        source_group: Optional source group (e.g. "prod_postgres_priority").

    Returns:
        GCS blob path string (without bucket name or gs:// prefix).
    """
    if source_type and source_group:
        return f"{configs_prefix}/{source_type}/{source_group}/{source_name}.yaml"
    return f"{configs_prefix}/{source_name}.yaml"


def load_config(
    source_name: str,
    db_name: str,
    tbl_name: str,
    gcs_bucket: str,
    project: str,
    configs_prefix: str = "configs",
    source_type: str | None = None,
    source_group: str | None = None,
) -> PipelineConfig:
    """Load and validate a PipelineConfig from a GCS cluster YAML file.

    Downloads the cluster-level config file, parses it as a ClusterConfig,
    then extracts and maps the specific db_name/tbl_name entry to a flat
    PipelineConfig.

    Args:
        source_name: Source cluster name (YAML file stem, secret key prefix).
        db_name: Database or schema name to extract.
        tbl_name: Table name to extract (surrounding quotes are stripped).
        gcs_bucket: GCS bucket name (without gs:// prefix).
        project: GCP project ID (used for secret name and BQ target).
        configs_prefix: Prefix inside the bucket where configs live.
        source_type: Optional. When set alongside source_group, enables the
            hierarchical GCS path layout:
            <configs_prefix>/<source_type>/<source_group>/<source_name>.yaml
        source_group: Optional. See source_type.

    Returns:
        Validated PipelineConfig instance.

    Raises:
        google.cloud.exceptions.NotFound: If the config file does not exist.
        pydantic.ValidationError: If the YAML does not match the schema.
        KeyError: If db_name or tbl_name is not present in the cluster YAML.
    """
    blob_path = _build_blob_path(source_name, configs_prefix, source_type, source_group)
    logger.info("Loading config from gs://%s/%s", gcs_bucket, blob_path)
    raw = _read_gcs_yaml(gcs_bucket, blob_path)

    cluster = ClusterConfig.model_validate(raw)
    return _build_pipeline_config(cluster, db_name, tbl_name, project, gcs_bucket)


# ---------------------------------------------------------------------------
# Secret resolution
# ---------------------------------------------------------------------------


def resolve_secret(secret_resource_name: str) -> str:
    """Fetch a secret payload from GCP Secret Manager.

    Args:
        secret_resource_name: Full resource name, e.g.
            projects/my-project/secrets/my-secret/versions/latest

    Returns:
        Decoded secret string.
    """
    client = secretmanager.SecretManagerServiceClient()
    response = client.access_secret_version(name=secret_resource_name)
    return response.payload.data.decode("utf-8")
