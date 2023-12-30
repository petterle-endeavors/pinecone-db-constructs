"""Defines the PineconeDBSetupLambda class and handler."""
from enum import Enum
from typing import List, Optional, Set

import pinecone
from pydantic import BaseModel, Field, model_validator, validator
from pydantic_settings import BaseSettings
from typing_extensions import TypedDict
from aws_lambda_powertools.utilities.typing import LambdaContext


class PineconeDBSetupCustomResource(CustomResourceInterface):
    """Define the Lambda function for initializing the database."""

    def __init__(
        self,
        event: CloudFormationCustomResourceEvent,  # type: ignore
        context: LambdaContext,  # type: ignore
        settings: PineconeDBSettings,
    ) -> None:
        super().__init__(event, context)
        password = self.get_secret(settings.api_key_secret_name)
        assert isinstance(password, str), "Pinecone API key must be a string."
        self._settings = settings
        pinecone.init(
            api_key=password,
            environment=settings.environment,
        )
        self._index_name_prefix = (
            f"{self._stack_name[:NUM_CHARS_TO_USE_FROM_STACK_NAME]}-"
            f"{self._stack_name_hash[:NUM_CHARS_TO_USE_FROM_STACK_NAME_HASH]}-"
        )
        self._add_stack_namespace_to_index_names()

    def _get_managed_index_names(self) -> Set[str]:
        """Get the managed index names."""
        index_names: List[str] = pinecone.list_indexes()
        managed_index_names = {
            index_name for index_name in index_names if index_name.startswith(self._index_name_prefix)
        }
        return managed_index_names

    def _add_stack_namespace_to_index_names(self) -> None:
        """
        Add the stack namespace to the index names.

        This allows us to have multiple stacks in the same environment without having to worry about index name
        collisions. On updates, we'll check the index name prefix to determine if the index is managed by the current
        stack.
        """
        prefix_len = len(self._index_name_prefix)
        for index_config in self._settings.indexes:
            index_config.name = f"{self._index_name_prefix}{index_config.name[:MAX_INDEX_NAME_LENGTH - prefix_len]}"

    def _create_resource(self) -> None:
        for index_config in self._settings.indexes:
            self._create_index(index_config)

    def _update_resource(self) -> None:
        managed_index_names = self._get_managed_index_names()
        new_indexes = set(index.name for index in self._settings.indexes)
        for index_name in managed_index_names - new_indexes:
            self._delete_index(index_name)
        for index_config in self._settings.indexes:
            if index_config.name in managed_index_names:
                self._update_index(index_config)
            else:
                self._create_index(index_config)

    def _delete_resource(self) -> None:
        managed_index_names = self._get_managed_index_names()
        for index in managed_index_names:
            self._delete_index(index)

    def _create_index(self, index_settings: PineconeIndexConfig) -> None:
        logger.info(f"Creating index '{index_settings.name}'")
        pinecone_options = index_settings.model_dump(
            exclude_none=True,
            exclude={"pod_size", "pod_instance_type"},
        )
        self._run_operation_with_retry(
            pinecone.create_index,
            **pinecone_options,
        )

    def _update_index(self, index_settings: PineconeIndexConfig) -> None:
        self._validate_update_operation(index_settings)
        self._run_operation_with_retry(
            pinecone.configure_index,
            index_settings.name,
            index_settings.replicas,
            index_settings.pod_type,
        )

    def _validate_update_operation(self, index_settings: PineconeIndexConfig) -> None:
        pod_type = pinecone.describe_index(index_settings.name).pod_type
        current_pod_size = self._get_pod_size(pod_type)
        new_pod_size = self._get_pod_size(index_settings.pod_type)
        assert (
            new_pod_size >= current_pod_size
        ), f"Cannot downgrade pod size. Current pod size: {current_pod_size}, new pod size: {new_pod_size}"
        current_pod_type = self._get_pod_type(pod_type)
        new_pod_type = self._get_pod_type(index_settings.pod_type)
        assert (
            current_pod_type == new_pod_type
        ), f"Cannot change pod type. Current pod type: {current_pod_type}, new pod type: {new_pod_type}"

    def _get_pod_type(self, pod_type: str) -> str:
        """Pod type is in the format s1.x1, so we need to split and get the first prefix (Example: s1)."""
        return pod_type.split(".")[0]

    def _get_pod_size(self, pod_type: str) -> int:
        """Pod type is in the format s1.x1, so we need to split and get the number."""
        return int(pod_type.split(".")[1][1:])

    def _delete_index(self, index: str) -> None:
        if self._can_delete_index(index):
            self._run_operation_with_retry(
                pinecone.delete_index,
                index,
            )

    def _can_delete_index(self, index_name: str) -> bool:
        """Validate that the index can be deleted."""
        try:
            index: pinecone.Index = pinecone.Index(index_name)
            stats = index.describe_index_stats()
        except Exception as error:  # pylint: disable=broad-except
            logger.warning(f"Failed to get index stats for index {index_name}. Error: {error}")
            return False
        if self._settings.pinecone_removal_policy == RemovalPolicy.RETAIN:
            logger.info(
                f"Skipping deletion of index {index} because the removal policy is set to {self._settings.pinecone_removal_policy}."
            )
            return False
        if self._settings.pinecone_removal_policy == RemovalPolicy.RETAIN_ON_UPDATE_OR_DELETE:
            if stats["total_vector_count"] > 0:
                logger.info(
                    f"Skipping deletion of index {index} because the removal policy is set to {self._settings.pinecone_removal_policy} and the index is not empty."
                )
                return False
        if self._settings.pinecone_removal_policy == RemovalPolicy.SNAPSHOT:
            self._create_snapshot(index_name)
        logger.info(f"Index {index} can be deleted.")
        return True

    def _create_snapshot(self, index_name: str) -> None:
        pinecone.create_collection(name=f"{index_name}_snapshot", source=index_name)
