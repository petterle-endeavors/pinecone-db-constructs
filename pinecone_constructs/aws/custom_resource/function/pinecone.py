"""Define CUD operations for a pinecone index."""
from typing import Callable
import time
import logging
from pinecone import create_index, init
from aws_lambda_powertools.utilities import parameters
from .settings import Settings
from .pinecone_settings import PineconeIndexSettings


LOGGER = logging.getLogger(__name__)


class PineconeIndex:
    """Define CUD operations for a pinecone index."""

    def __init__(
        self,
        settings: Settings,
        index_settings: PineconeIndexSettings,
    ) -> None:
        """Initialize the index."""
        self._index_settings = index_settings
        self._settings = settings
        key = parameters.get_secret(
            index_settings.api_key_secret_name,
            max_age=30,
        )
        assert isinstance(key, str), f"api_key of type '{type(key)}' returned from " \
            "secrets manager is not a string"
        init(
            api_key=key,
            environment=index_settings.environment,
        )

    @property
    def name(self) -> str:
        """Return the name of the index."""
        return self._index_settings.name

    def create(self) -> None:
        """Create a pinecone index."""
        settings = self._index_settings
        self.run_operation_with_retry(
            create_index,
            name=settings.name,
            dimension=settings.dimension,
            metric=settings.metric,
            pods=settings.pods,
            replicas=settings.replicas,
            pod_type=f"{settings.pod_instance_type}.{settings.pod_size}",
            metadata_config=settings.metadata_config,
            source_collection=settings.source_collection,
        )

    def run_operation_with_retry(self, operation: Callable, *args, **kwargs) -> None:
        """Run an operation with retries."""
        num_attempts = self._settings.num_attempts_to_run_operation
        delay_between_attempts = 5
        for attempt in range(num_attempts):
            try:
                operation(*args, **kwargs)
                return
            except Exception as error:  # pylint: disable=broad-except
                LOGGER.error(error)
                LOGGER.info("Attempt %s of %s failed.", attempt + 1, num_attempts)
                if attempt + 1 == num_attempts:
                    raise RuntimeError(f"Failed to run operation: {operation.__name__}") from error
                LOGGER.info("Retrying in %s seconds...", delay_between_attempts)
                time.sleep(delay_between_attempts)
