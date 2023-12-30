"""Define the lambda function for initializing the Pinecone database."""
import logging
from typing import Union
from crhelper import CfnResource
from .settings import PineconeDBSettings
from .helpers import get_index_name_from_event

LOGGER = logging.getLogger(__name__)

helper = CfnResource(
    json_logging=True,
    log_level="DEBUG",
    boto_level="CRITICAL",
    # polling_interval=1,
)


try:
    SETTINGS = PineconeDBSettings()  # type: ignore
except Exception as e:  # pylint: disable=broad-except
    helper.init_failure(e)
    raise e


@helper.create
def create(event, _context) -> Union[bool, str, None]:
    """Create the Pinecone database."""
    index_name = SETTINGS.index_config.name or get_index_name_from_event(event)  # pylint: disable=no-member
    LOGGER.info("Creating Pinecone index '%s'", index_name)


@helper.update
def update(event, _context) -> Union[bool, str, None]:
    """Update the Pinecone database."""
    index_name = SETTINGS.index_config.name or get_index_name_from_event(event) # pylint: disable=no-member
    LOGGER.info("Updating Pinecone index '%s'", index_name)


@helper.delete
def delete(event, _context) -> Union[bool, str, None]:
    """Delete the Pinecone database."""
    index_name = SETTINGS.index_config.name or get_index_name_from_event(event) 
    LOGGER.info("Deleting Pinecone index '%s'", index_name)


def handler(event, context):
    """Handle the lambda event."""
    helper(event, context)
