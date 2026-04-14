"""Abstract base class for all pipeline extractors.

To add a new source type:
1. Create a new module in pipeline/extractors/ (e.g. mysql.py).
2. Subclass BaseExtractor and implement extract().
3. Register the class in pipeline/registry.py under EXTRACTOR_REGISTRY.
4. Add the source type value to pipeline/config.py SourceType enum.
"""

import logging
from abc import ABC, abstractmethod

from pyspark.sql import DataFrame, SparkSession

from pipeline.config import PipelineConfig

logger = logging.getLogger(__name__)


class BaseExtractor(ABC):
    """Contract that every extractor must fulfil.

    Extractors are stateless; all configuration is passed via PipelineConfig.
    """

    @abstractmethod
    def extract(self, spark: SparkSession, config: PipelineConfig) -> DataFrame:
        """Extract data from the source and return a Spark DataFrame.

        Args:
            spark: Active SparkSession.
            config: Validated pipeline configuration for this run.

        Returns:
            DataFrame containing the extracted data.

        Raises:
            Exception: Any extraction-specific error (JDBC failure, auth
                error, etc.) is allowed to propagate so the caller can
                handle or log it.
        """
        ...
