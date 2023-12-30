"""Define some helper functions for the pinecone custom resource."""

from typing import Any, Dict


def get_index_name_from_event(event: Dict[str, Any]) -> str:
    """Get the index name from the event."""
    stack_arn: str = event["StackId"]
    logical_resource_id: str = event["LogicalResourceId"]
    # extract the region, account number, stack name, and logical resource id
    # from the stack arn
    _, _, region, acount_id, _, stack_name, _ = stack_arn.split(":")
    return f"{region}:{acount_id}:{stack_name}:{logical_resource_id}"
