"""Pipeline configuration: YAML schema (Pydantic) and GCS loader.

Config files are stored at:
  gs://<bucket>/configs/<source_name>/<db_name>/<tbl_name>.yaml

Secrets (JDBC URLs, passwords) are stored in GCP Secret Manager and
referenced by their resource name in the YAML, never inline.
"""

import logging
from enum import Enum
from typing import Any

import yaml
from google.cloud import secretmanager, storage
from pydantic import BaseModel, Field, model_validator

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


class WriteMode(str, Enum):
    """BigQuery write modes."""

    OVERWRITE = "overwrite"
    APPEND = "append"
    MERGE = "merge"


class ExtractionMode(str, Enum):
    """Extraction strategy."""

    FULL = "full"
    INCREMENTAL = "incremental"


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------


class SourceConfig(BaseModel):
    """Source connection configuration."""

    type: SourceType

    # Postgres-specific (ignored for other source types)
    jdbc_url_secret: str | None = Field(
        default=None,
        description=(
            "GCP Secret Manager resource name for the JDBC URL. "
            "Format: projects/<project>/secrets/<name>/versions/latest"
        ),
    )
    table: str | None = Field(
        default=None,
        description="Fully qualified source table, e.g. public.users",
    )
    partition_column: str | None = Field(
        default=None,
        description="Column used to parallelise JDBC reads via numPartitions.",
    )
    lower_bound: int | None = Field(
        default=None,
        description="Lower bound for JDBC partition column (required if partition_column set).",
    )
    upper_bound: int | None = Field(
        default=None,
        description="Upper bound for JDBC partition column (required if partition_column set).",
    )
    num_partitions: int = Field(
        default=10,
        description="Number of JDBC read partitions.",
    )
    fetch_size: int = Field(
        default=10000,
        description="JDBC fetchSize (rows per round trip).",
    )

    @model_validator(mode="after")
    def validate_source_fields(self) -> "SourceConfig":
        if self.type == SourceType.POSTGRES:
            missing = [f for f in ("jdbc_url_secret", "table") if not getattr(self, f)]
            if missing:
                raise ValueError(f"Postgres source requires: {', '.join(missing)}")
        return self


class TargetConfig(BaseModel):
    """BigQuery target configuration."""

    project: str = Field(description="GCP project ID for the target dataset.")
    dataset: str = Field(description="BigQuery dataset name.")
    table: str = Field(description="BigQuery table name.")
    write_mode: WriteMode = Field(
        default=WriteMode.OVERWRITE,
        description="How to write data into the target table.",
    )
    merge_keys: list[str] = Field(
        default_factory=list,
        description=(
            "Columns that uniquely identify a row for upsert (write_mode=merge). "
            "Required when write_mode is merge. Example: [id] or [user_id, event_time]."
        ),
    )
    partition_field: str | None = Field(
        default=None,
        description="Column used for BigQuery time partitioning.",
    )
    clustering_fields: list[str] = Field(
        default_factory=list,
        description="Columns used for BigQuery clustering (max 4).",
    )

    @model_validator(mode="after")
    def validate_merge_keys(self) -> "TargetConfig":
        if self.write_mode == WriteMode.MERGE and not self.merge_keys:
            raise ValueError(
                "write_mode=merge requires merge_keys to be set in the target config."
            )
        return self

    @property
    def full_table_id(self) -> str:
        """Return project.dataset.table format."""
        return f"{self.project}.{self.dataset}.{self.table}"


class ExtractionConfig(BaseModel):
    """Extraction strategy configuration."""

    mode: ExtractionMode = Field(default=ExtractionMode.FULL)
    watermark_column: str | None = Field(
        default=None,
        description="Column used as high-watermark for incremental extraction.",
    )
    watermark_table: str | None = Field(
        default=None,
        description=(
            "BigQuery table (project.dataset.table) that stores the last "
            "watermark value. Defaults to <target.dataset>._watermarks."
        ),
    )


# ---------------------------------------------------------------------------
# Root config model
# ---------------------------------------------------------------------------


class PipelineConfig(BaseModel):
    """Root pipeline configuration loaded from a GCS YAML file."""

    source_name: str = Field(description="Logical source group name.")
    db_name: str = Field(description="Database or schema name.")
    tbl_name: str = Field(description="Table name.")

    source: SourceConfig
    target: TargetConfig
    extraction: ExtractionConfig = Field(default_factory=ExtractionConfig)

    # Carry-through metadata
    extra: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary extra metadata (not used by the pipeline).",
    )


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------


def _read_gcs_yaml(bucket_name: str, blob_path: str) -> dict:
    """Download and parse a YAML file from GCS."""
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_path)
    content = blob.download_as_text()
    return yaml.safe_load(content)


def load_config(
    source_name: str,
    db_name: str,
    tbl_name: str,
    gcs_bucket: str,
    configs_prefix: str = "configs",
) -> PipelineConfig:
    """Load and validate a PipelineConfig from GCS.

    Args:
        source_name: Logical source group (maps to a top-level configs folder).
        db_name: Database or schema name.
        tbl_name: Table name.
        gcs_bucket: GCS bucket name (without gs:// prefix).
        configs_prefix: Prefix inside the bucket where configs live.

    Returns:
        Validated PipelineConfig instance.

    Raises:
        google.cloud.exceptions.NotFound: If the config file does not exist.
        pydantic.ValidationError: If the YAML does not match the schema.
    """
    blob_path = f"{configs_prefix}/{source_name}/{db_name}/{tbl_name}.yaml"
    logger.info("Loading config from gs://%s/%s", gcs_bucket, blob_path)
    raw = _read_gcs_yaml(gcs_bucket, blob_path)

    # Inject identity fields so the config is self-describing
    raw.setdefault("source_name", source_name)
    raw.setdefault("db_name", db_name)
    raw.setdefault("tbl_name", tbl_name)

    return PipelineConfig.model_validate(raw)


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
