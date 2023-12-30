"""Define the lambda function for initializing the Pinecone database."""
import copy
import logging
from typing import Any, Dict, Union
from crhelper import CfnResource, FAILED

from aws_lambda_powertools.utilities.typing import LambdaContext
from .pinecone_settings import PineconeIndexSettings
from .settings import Settings
from .pinecone import PineconeIndex

LOGGER = logging.getLogger(__name__)

helper = CfnResource(
    json_logging=True,
    log_level="INFO",
    boto_level="CRITICAL",
    # polling_interval=1,
)

SETTINGS: Union[Settings, None] = None
try:
    SETTINGS = Settings()  # type: ignore
except Exception as error:  # pylint: disable=broad-except
    helper.init_failure(error)


@helper.create
def create(_: Dict[str, Any], context: LambdaContext) -> Union[bool, str, None]:
    """Create the Pinecone database."""
    index: PineconeIndex = context.index # type: ignore
    LOGGER.info("Creating Pinecone index '%s'", index.name)
    index.create()


@helper.update
def update(_: Dict[str, Any], context: LambdaContext) -> Union[bool, str, None]:
    """Update the Pinecone database."""
    index: PineconeIndex = context.index # type: ignore
    LOGGER.info("Updating Pinecone index '%s'", index.name)


@helper.delete
def delete(_: Dict[str, Any], context: LambdaContext) -> Union[bool, str, None]:
    """Delete the Pinecone database."""
    index: PineconeIndex = context.index # type: ignore
    LOGGER.info("Deleting Pinecone index '%s'", index.name)


def lambda_handler(event: dict, context: LambdaContext):
    """Handle the lambda event."""
    assert SETTINGS is not None, "SETTINGS is None"
    index_settings = PineconeIndexSettings.model_validate(event["ResourceProperties"])
    settings = copy.deepcopy(SETTINGS)
    context.index = PineconeIndex(  # type: ignore
        settings=copy.deepcopy(SETTINGS),
        index_settings=index_settings,
    )
    helper(event, context)
    if helper.Status == FAILED:
        raise RuntimeError(f"Failed to create custom resource: {helper.Reason}")
