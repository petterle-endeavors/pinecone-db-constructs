"""Create a CDK app for deploying the Pinecone custom resource."""
from aws_cdk import Stack, App
from pinecone_constructs.aws.construct import PineconeIndex
from pinecone_constructs.aws.custom_resource.function.pinecone_settings import (
    PineconeIndexSettings,
    PineConeEnvironment,
)


class PineconeStack(Stack):
    """Define the Pinecone stack."""

    def __init__(self, scope: App, stack_id: str, **kwargs) -> None:
        """Initialize the Pinecone stack."""
        super().__init__(scope, stack_id, **kwargs)
        PineconeIndex(
            self,
            "PineconeIndex",
            PineconeIndexSettings(
                api_key_secret_name="pinecone-test",
                environment=PineConeEnvironment.GCP_STARTER,
                dimension=384,
                name="pinecone-test",
            ),
        )


APP = App()
PineconeStack(APP, "pinecone-stack")
APP.synth()
