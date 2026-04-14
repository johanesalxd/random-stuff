"""Abstract base class for all pipeline writers.

To add a new target type:
1. Create a new module in pipeline/writers/ (e.g. gcs.py).
2. Subclass BaseWriter and implement write().
3. Register the class in pipeline/registry.py under WRITER_REGISTRY.
"""

from abc import ABC, abstractmethod

from pyspark.sql import DataFrame

from pipeline.config import PipelineConfig


class BaseWriter(ABC):
    """Contract that every writer must fulfil.

    Writers are stateless; all configuration is passed via PipelineConfig.
    """

    @abstractmethod
    def write(self, df: DataFrame, config: PipelineConfig) -> None:
        """Write a DataFrame to the target.

        Args:
            df: DataFrame produced by the extractor.
            config: Validated pipeline configuration for this run.

        Raises:
            Exception: Any write-specific error is allowed to propagate.
        """
        ...
