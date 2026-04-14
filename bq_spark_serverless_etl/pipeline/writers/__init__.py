"""Writer implementations for supported target types."""

from pipeline.writers.base import BaseWriter
from pipeline.writers.bigquery import BigQueryWriter

__all__ = [
    "BaseWriter",
    "BigQueryWriter",
]
