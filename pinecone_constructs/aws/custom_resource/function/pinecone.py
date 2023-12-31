"""Define CUD operations for a pinecone index."""
import copy
from typing import Callable
import time
import logging
import pinecone
from aws_lambda_powertools.utilities import parameters
from .settings import Settings
from .pinecone_settings import PineconeIndexSettings, RemovalPolicy


LOGGER = logging.getLogger(__name__)


class PineconeIndex:
    """Define CUD operations for a pinecone index."""

    def __init__(
        self,
        settings: Settings,
        index_settings: PineconeIndexSettings,
    ) -> None:
        """Initialize the index."""
        self._index_settings = copy.deepcopy(index_settings)
        self._settings = copy.deepcopy(settings)
        key = parameters.get_secret(
            index_settings.api_key_secret_name,
            max_age=30,
        )
        assert isinstance(key, str), f"api_key of type '{type(key)}' returned from " \
            "secrets manager is not a string"
        pinecone.init(
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
            pinecone.create_index,
            name=settings.name,
            dimension=settings.dimension,
            metric=settings.metric,
            pods=settings.pods,
            replicas=settings.replicas,
            pod_type=f"{settings.pod_instance_type}.{settings.pod_size}",
            metadata_config=settings.metadata_config,
            source_collection=settings.source_collection,
        )

    def delete(self) -> None:
        """Delete the pinecone index."""
        if self._can_delete_index():
            self.run_operation_with_retry(
                pinecone.delete_index,
                name=self._index_settings.name,
            )

    def _can_delete_index(self) -> bool:
        """Validate that the index can be deleted."""
        index_name = self._index_settings.name
        removal_policy = self._index_settings.removal_policy
        try:
            index = pinecone.Index(index_name)
            stats = index.describe_index_stats()
        except Exception as error:  # pylint: disable=broad-except
            msg = f"Failed to get index stats for index '{index_name}'. Error: {error}"
            raise RuntimeError(msg) from error
        if removal_policy == RemovalPolicy.RETAIN.value:
            msg = "Skipping deletion of index '%s' because the removal policy is set to %s."
            LOGGER.info(msg, index_name, removal_policy)
            return False
        if removal_policy == RemovalPolicy.RETAIN_ON_UPDATE_OR_DELETE.value:
            if stats["total_vector_count"] > 0:
                msg = "Skipping deletion of index '%s' because the removal policy is set to %s and the index is not empty."
                LOGGER.info(msg, index_name, removal_policy)
                return False
        if removal_policy == RemovalPolicy.SNAPSHOT.value:
            self._create_snapshot(index_name)
        LOGGER.info("Index '%s' can be deleted.", index_name)
        return True

    def _create_snapshot(self, index_name: str) -> None:
        self.run_operation_with_retry(
            pinecone.create_collection,
            name=f"{index_name}_snapshot",
            source=index_name,
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
