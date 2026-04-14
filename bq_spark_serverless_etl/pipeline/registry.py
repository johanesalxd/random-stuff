"""Extractor and writer registries.

Adding a new source type:
1. Create pipeline/extractors/<name>.py subclassing BaseExtractor.
2. Import it here and add an entry to EXTRACTOR_REGISTRY.
3. Add the source type string to SourceType in pipeline/config.py.

Adding a new target type:
1. Create pipeline/writers/<name>.py subclassing BaseWriter.
2. Import it here and add an entry to WRITER_REGISTRY.
"""

from pipeline.config import SourceType
from pipeline.extractors.base import BaseExtractor
from pipeline.extractors.postgres import PostgresExtractor
from pipeline.writers.base import BaseWriter
from pipeline.writers.bigquery import BigQueryWriter

# ---------------------------------------------------------------------------
# Extractor registry
# ---------------------------------------------------------------------------
# Maps SourceType enum values to their extractor implementations.
# All targets currently write to BigQuery, so only one writer registry entry
# exists for now. Expand when GCS or other targets are needed.

EXTRACTOR_REGISTRY: dict[SourceType, type[BaseExtractor]] = {
    SourceType.POSTGRES: PostgresExtractor,
    # SourceType.MYSQL: MySQLExtractor,            # future
    # SourceType.COCKROACHDB: CockroachDBExtractor, # future (same as Postgres JDBC, different driver)
}

# ---------------------------------------------------------------------------
# Writer registry
# ---------------------------------------------------------------------------

WRITER_REGISTRY: dict[str, type[BaseWriter]] = {
    "bigquery": BigQueryWriter,
    # "gcs": GCSWriter,   # future
}

_DEFAULT_WRITER = "bigquery"


def get_extractor(source_type: SourceType) -> BaseExtractor:
    """Instantiate the extractor for the given source type.

    Args:
        source_type: SourceType enum value from the pipeline config.

    Returns:
        Instantiated extractor.

    Raises:
        KeyError: If source_type is not registered.
    """
    cls = EXTRACTOR_REGISTRY.get(source_type)
    if cls is None:
        registered = [s.value for s in EXTRACTOR_REGISTRY]
        raise KeyError(
            f"No extractor registered for source type '{source_type.value}'. "
            f"Registered types: {registered}"
        )
    return cls()


def get_writer(writer_type: str = _DEFAULT_WRITER) -> BaseWriter:
    """Instantiate a writer by type name.

    Args:
        writer_type: Writer key string (default: "bigquery").

    Returns:
        Instantiated writer.

    Raises:
        KeyError: If writer_type is not registered.
    """
    cls = WRITER_REGISTRY.get(writer_type)
    if cls is None:
        registered = list(WRITER_REGISTRY)
        raise KeyError(
            f"No writer registered for type '{writer_type}'. "
            f"Registered types: {registered}"
        )
    return cls()
