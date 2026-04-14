"""Extractor implementations for supported source types."""

from pipeline.extractors.base import BaseExtractor
from pipeline.extractors.postgres import PostgresExtractor

__all__ = [
    "BaseExtractor",
    "PostgresExtractor",
]
