"""Define the Pinecone database construct."""
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Union

from aws_cdk import CustomResource, Duration, RemovalPolicy
from aws_cdk import Size as StorageSize
from aws_cdk import aws_iam as iam
from aws_cdk import custom_resources as cr
from constructs import Construct
from pydantic_settings import BaseSettings

from .custom_resource.function.settings import (
    PineconeDBSettings,
)



CONSTRUCTS_DIR = Path(__file__).parent
PINECONE_CUSTOM_RESOURCE_DIR = CONSTRUCTS_DIR / "custom_resources" / "pinecone_db"
CUSTOM_RESOURCE_DIRECTORY = CONSTRUCTS_DIR / "custom_resources"


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
    timeout: int = 5
    ephemeral_storage_size_mb: int = 512


class PineconeDatabase(Construct):
    """Define the Pinecone database construct."""

    def __init__(  # pylint: disable=too-many-arguments
        self,
        scope: Construct,
        construct_id: str,
        db_settings: PineconeDBSettings,
        resource_namer: Callable,
        removal_policy: RemovalPolicy = RemovalPolicy.RETAIN,
        **kwargs,
    ) -> None:
        """Initialize the Pinecone database construct."""
        super().__init__(scope, construct_id, **kwargs)
        self._namer = resource_namer
        # We want to pass the removal policy to the custom resource
        db_settings.pinecone_removal_policy = removal_policy.value  # type: ignore
        self._secret_arn = get_secret_arn_from_name(db_settings.api_key_secret_name)
        self._db_settings = db_settings
        self.custom_resource_provider = self._create_custom_resource()

    def _create_custom_resource(self) -> cr.Provider:
        config = self._get_lambda_config()
        name = config.function_name
        python_lambda = PythonLambda.get_lambda_function(
            self,
            construct_id=f"custom-resource-lambda-{name}",
            config=config,
        )
        python_lambda.add_to_role_policy(
            statement=iam.PolicyStatement(
                actions=["secretsmanager:GetSecretValue"],
                effect=iam.Effect.ALLOW,
                resources=[self._secret_arn],
            )
        )
        provider: cr.Provider = cr.Provider(
            self,
            id="custom-resource-provider",
            on_event_handler=python_lambda.lambda_function,  # type: ignore
            provider_function_name=name + "-PROVIDER",
        )
        CustomResource(
            self,
            id="custom-resource",
            service_token=provider.service_token,
            properties={
                "custom_resource_dir_hash": get_hash_for_all_files_in_dir(CUSTOM_RESOURCE_DIRECTORY),
                "settings": self._db_settings.model_dump_json(),
            },
        )
        return provider

    def _get_lambda(self, config: LambdaConfig) -> lambda_alpha.PythonFunction:
        index_directory = Path(config.index_directory)
        python_runtime = _lambda.Runtime.PYTHON_3_11
        lambda_function = lambda_alpha.PythonFunction(
            self,
            config.construct_id,
            description=config.description,
            entry=str(index_directory.resolve().as_posix()),
            runtime=python_runtime,
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
            environment=self._serialize_env(config.environment) if config.environment else None,
        )
        if config.function_url_config:
            function_url = lambda_function.add_function_url(
                cors=_lambda.FunctionUrlCorsOptions(allowed_origins=["*"], allowed_headers=["*"]),
                auth_type=config.function_url_config.auth_type,
                invoke_mode=_lambda.InvokeMode.BUFFERED,
            )
            CfnOutput(
                self,
                f"{config.construct_id}Url",
                value=function_url.url,
                description=f"URL for the {config.construct_id} Lambda function.",
            )
        return lambda_function