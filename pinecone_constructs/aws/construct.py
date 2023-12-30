"""Define the Pinecone database construct."""
import json
from hashlib import md5
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union, List

from aws_cdk import CustomResource, Duration
from aws_cdk.aws_secretsmanager import Secret
from aws_cdk.aws_iam import PolicyStatement
from aws_cdk import aws_lambda_python_alpha as lambda_alpha
from aws_cdk import aws_lambda as _lambda
from aws_cdk import (
    Size,
    CfnOutput,
)
from aws_cdk import custom_resources as cr
from constructs import Construct
from pydantic_settings import BaseSettings
from pydantic import BaseModel

from .custom_resource.function.pinecone_settings import (
    PineconeIndexSettings,
    MAX_INDEX_NAME_LENGTH,
)
from .custom_resource.function.settings import Settings as RuntimeSettings



_CUSTOM_RESOURCE_DIRECTORY = Path(__file__).parent / "custom_resource"


class PineconeIndex(Construct):
    """Define the Pinecone database construct."""

    # pylint: disable=too-many-instance-attributes
    @dataclass
    class LambdaConfig:
        """Lambda function configuration."""

        construct_id: str
        description: str
        index_directory: Union[str, Path]
        index_module_name: str = "function/index.py"
        handler: str = "lambda_handler"
        environment: Optional[BaseSettings] = None
        memory_size_mb: int = 256
        timeout: int = 120
        ephemeral_storage_size_mb: int = 512

    def __init__(  # pylint: disable=too-many-arguments
        self,
        scope: Construct,
        construct_id: str,
        index_settings: Union[List[PineconeIndexSettings], PineconeIndexSettings],
        **kwargs,
    ) -> None:
        """Initialize the Pinecone database construct."""
        super().__init__(scope, construct_id, **kwargs)
        if not isinstance(index_settings, list):
            index_settings = [index_settings]
        self._index_settings = index_settings
        self.custom_resource_provider = self._create_custom_resource(
            self.LambdaConfig(
                construct_id=f"{construct_id}Lambda",
                description="Custom resource provider for configuring Pinecone indexes.",
                index_directory=_CUSTOM_RESOURCE_DIRECTORY,
                environment=RuntimeSettings()
            )
        )

    def _create_custom_resource(self, func_config: LambdaConfig) -> cr.Provider:
        function = self._get_lambda(func_config)
        provider: cr.Provider = cr.Provider(
            self,
            id=f"{func_config.construct_id}Provider",
            on_event_handler=function,  # type: ignore
        )
        for index_settings in self._index_settings:
            index_settings.name = self.get_index_name(provider, index_settings)
            properties = self.serialize_env(index_settings)
            # we are adding these properties so that cloudformation will
            # update the custom resource when either the settings have changed
            # or the custom resource directory has changed, i.e. the lambda
            # function code has changed
            properties["custom_resource_dir_hash"] = self.get_hash_for_all_files_in_dir(_CUSTOM_RESOURCE_DIRECTORY)
            api_key_secret = Secret.from_secret_name_v2(self, "PineconeApiKey", index_settings.api_key_secret_name)
            api_key_secret.grant_read(function)
            CustomResource(
                self,
                id=f"{func_config.construct_id}CustomResource",
                service_token=provider.service_token,
                properties=properties,
            )
            CfnOutput(
                self,
                f"{index_settings.name}IndexName",
                value=index_settings.name,
                description=f"Name of the '{index_settings.name}' Pinecone index.",
            )
        return provider

    @staticmethod
    def get_index_name(provider: cr.Provider, index_settings: PineconeIndexSettings) -> str:
        """Get the index name."""
        prefix = md5(provider.service_token.encode()).hexdigest()[:20]
        index_name = index_settings.name
        name = f"{prefix}-{index_name}"
        return name[:MAX_INDEX_NAME_LENGTH]

    @staticmethod
    def add_polling_permissions_to_lambda(
        lambda_function: Union[lambda_alpha.PythonFunction, _lambda.Function],
    ) -> None:
        """
        Add permissions to the lambda function to allow it to poll for the custom resource.

        Args:
            lambda_function: The lambda function to add the permissions to.

        """
        lambda_function.add_to_role_policy(
            statement=PolicyStatement(
                actions=[
                    "lambda:AddPermission",
                    "lambda:RemovePermission",
                    "events:PutRule",
                    "events:DeleteRule",
                    "events:PutTargets",
                    "events:RemoveTargets",
                ],
                resources=["*"],
            )
        )

    def _get_lambda(self, config: LambdaConfig) -> lambda_alpha.PythonFunction:
        index_directory = Path(config.index_directory)
        lambda_function = lambda_alpha.PythonFunction(
            self,
            config.construct_id,
            description=config.description,
            entry=str(index_directory.resolve().as_posix()),
            runtime=_lambda.Runtime.PYTHON_3_11,
            bundling=lambda_alpha.BundlingOptions(
                # this is needed because we are running ARM
                # if we were running x86, we would NOT need any bundling
                # options as the PythonFunction construct takes care of this for us
                environment={
                    "PIP_PLATFORM": "manylinux2014_aarch64",
                    "PIP_ONLY_BINARY": ":all:",
                },
            ),
            index=config.index_module_name,
            handler=config.handler,
            architecture=_lambda.Architecture.ARM_64,
            timeout=Duration.seconds(config.timeout),
            memory_size=config.memory_size_mb,
            ephemeral_storage_size=Size.mebibytes(config.ephemeral_storage_size_mb),
            environment=self.serialize_env(config.environment) if config.environment else None,
        )
        CfnOutput(
            self,
            f"{config.construct_id}FunctionArn",
            value=lambda_function.function_arn,
            description=f"ARN for the {config.construct_id} Lambda function.",
        )
        return lambda_function

    @staticmethod
    def serialize_env(env: BaseModel) -> dict[str, str]:
        """
        Serialize the environment variables.
        
        This will serialize the pydantic settings into a dictionary that can be passed
        to any aws resource for the environment variables.

        Args:
            env: The pydantic settings object.
        
        Returns:
            The serialized environment variables.

        """
        obj = {
            key: value
            if isinstance(value, str)
            else json.dumps(value)
            for key, value in env.model_dump(mode="json", exclude_none=True).items()
        }
        return obj

    @staticmethod
    def get_hash_for_all_files_in_dir(directory: Path) -> str:
        """
        Get the hash for all files in a directory.

        Args:
            directory: The directory to get the hash for.

        Returns:
            The hash for all files in the directory.

        """
        raw_text = ""
        for file in directory.glob("**/*"):
            if file.is_file() and file.suffix in {".py", ".json"}:
                raw_text += file.read_text()
        return md5(raw_text.encode()).hexdigest()
