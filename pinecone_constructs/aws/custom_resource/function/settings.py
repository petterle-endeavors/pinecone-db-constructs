"""Pinecone index config settings."""
from enum import Enum
from typing import List, Optional, TypedDict
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings



class MetaDataConfig(TypedDict):
    """Define the metadata configuration for the Pinecone index."""

    field_names: List[str]


class PodType(str, Enum):
    """Define the pod types."""

    S1 = "s1"
    P1 = "p1"
    P2 = "p2"


class PodSize(str, Enum):
    """Define the pod sizes."""

    X1 = "x1"
    X2 = "x2"
    X4 = "x4"
    X8 = "x8"


class DistanceMetric(str, Enum):
    """Define the distance metrics."""

    EUCLIDEAN = "euclidean"
    COSINE = "cosine"
    DOT_PRODUCT = "dotproduct"


class RemovalPolicy(str, Enum):
    """Define the removal policies."""

    DESTROY = "DESTROY"
    RETAIN = "RETAIN"
    RETAIN_ON_UPDATE_OR_DELETE = "RETAIN_ON_UPDATE_OR_DELETE"
    SNAPSHOT = "SNAPSHOT"


class PineConeEnvironment(str, Enum):
    """Define the environments for the Pinecone project."""

    EAST_1 = "us-east-1-aws"


MAX_INDEX_NAME_LENGTH = 45
NUM_CHARS_TO_USE_FROM_STACK_NAME_HASH = 15
NUM_CHARS_TO_USE_FROM_STACK_NAME = 10


class PineconeIndexConfig(BaseSettings):
    """Define the settings for the Pinecone index."""

    name: Optional[str] = Field(
        default=None,
        description="We recommend leaving this blank to avoid name collisions.",
    )
    dimension: int = Field(
        ...,
        description="Dimension of vectors stored in the index.",
    )
    metric: Optional[DistanceMetric] = Field(
        default=DistanceMetric.DOT_PRODUCT,
        description="Distance metric used to compute the distance between vectors.",
    )
    pods: Optional[int] = Field(
        default=1,
        le=2,
        ge=1,
        description="Number of pods to use for the index.",
    )
    replicas: Optional[int] = Field(
        default=1,
        le=1,
        ge=1,
        description="Number of replicas to use for the index.",
    )
    pod_instance_type: Optional[PodType] = Field(
        default=PodType.S1,
        description="Type of pod to use for the index. (https://docs.pinecone.io/docs/indexes)",
    )
    pod_size: Optional[PodSize] = Field(
        default=PodSize.X1,
        description="Size of pod to use for the index. (https://docs.pinecone.io/docs/indexes)",
    )
    pod_type: str = Field(
        default="",
        description="Used internally to create a fully qualified pod type (Example: s1.x1)",
    )
    metadata_config: Optional[MetaDataConfig] = Field(
        default=None,
        description="Metadata configuration for the index.",
    )
    source_collection: Optional[str] = Field(
        default=None,
        description="Name of the source collection to use for the index.",
    )

    @model_validator(mode="after")
    def validate_pod_type(self) -> "PineconeIndexConfig":
        """Validate the pod type."""
        if self.pod_instance_type and self.pod_size:
            self.pod_type = f"{self.pod_instance_type.value}.{self.pod_size.value}"  # pylint: disable=no-member
            return self
        raise ValueError("Pod instance type and pod size must be set.")


class PineconeDBSettings(BaseSettings):
    """Define the settings for initializing the Pinecone database."""

    api_key_secret_name: str = Field(
        ...,
        description="The name of the secret containing the Pinecone API key.",
    )
    environment: PineConeEnvironment = Field(
        ...,
        description="The environment to use for the Pinecone project.",
    )
    index_config: PineconeIndexConfig = Field(
        ...,
        description="Config for the Pinecone index.",
    )
    removal_policy: RemovalPolicy = Field(
        default=RemovalPolicy.RETAIN,
        description="The removal policy for the Pinecone indexes.",
    )
