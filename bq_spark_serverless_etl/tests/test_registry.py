"""Unit tests for pipeline.registry -- extractor/writer lookup."""

import pytest

from pipeline.config import SourceType
from pipeline.extractors.postgres import PostgresExtractor
from pipeline.registry import get_extractor, get_writer
from pipeline.writers.bigquery import BigQueryWriter


def test_get_extractor_postgres():
    extractor = get_extractor(SourceType.POSTGRES)
    assert isinstance(extractor, PostgresExtractor)


def test_get_extractor_unregistered_raises():
    # Temporarily remove a registered type to exercise the KeyError guard.
    from pipeline.registry import EXTRACTOR_REGISTRY

    saved = EXTRACTOR_REGISTRY.pop(SourceType.POSTGRES)
    try:
        with pytest.raises(KeyError, match="No extractor registered"):
            get_extractor(SourceType.POSTGRES)
    finally:
        EXTRACTOR_REGISTRY[SourceType.POSTGRES] = saved


def test_get_writer_default_is_bigquery():
    writer = get_writer()
    assert isinstance(writer, BigQueryWriter)


def test_get_writer_explicit_bigquery():
    writer = get_writer("bigquery")
    assert isinstance(writer, BigQueryWriter)


def test_get_writer_unregistered_raises():
    with pytest.raises(KeyError, match="No writer registered"):
        get_writer("nonexistent")


def test_extractor_instances_are_fresh():
    """Each call returns a new instance (stateless, not a singleton)."""
    a = get_extractor(SourceType.POSTGRES)
    b = get_extractor(SourceType.POSTGRES)
    assert a is not b
