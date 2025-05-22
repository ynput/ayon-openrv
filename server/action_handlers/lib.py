import json
from typing import Any
from ayon_server.logging import logger
# from ayon_server.events.eventstream import EventStream
# from ayon_server.api.dependencies import (
#     dep_folder_id,
#     dep_product_id,
#     dep_version_id
# )

# Define equivalent functions using ayon_server API
async def get_folders(project_name, folder_ids=None, fields=None):
    folder_ids = folder_ids or []
    # Implementation using ayon_server API
    from ayon_server.entities import FolderEntity
    return [
        await FolderEntity.load(project_name, folder_id)
        for folder_id in folder_ids
]


async def get_products(project_name, product_ids=None, fields=None):
    product_ids = product_ids or []
    # Implementation using ayon_server API
    from ayon_server.entities import ProductEntity
    return [
        await ProductEntity.load(project_name, product_id)
        for product_id in product_ids
    ]


async def get_versions(project_name, version_ids=None, fields=None):
    version_ids = version_ids or []
    # Implementation using ayon_server API
    from ayon_server.entities import VersionEntity
    return [
        await VersionEntity.load(project_name, version_id)
        for version_id in version_ids
    ]


def prepare_delivery_version_data(
    version_id: str,
    comment: str,
    intent: str,
) -> dict[str, str]:
    return {
        "id": version_id,
        "comment": comment,
        "intent": intent,
    }


async def request_offloaded_process(
    project_name: str,
    preset_name: str,
    versions_data: list[dict[str, str]],
    sender: str,
    identifier: str,
    processing_type: str = "delivery",
    representation_data: dict[str, dict] = None,
):
    """Request delivery for given versions in project.

    Args:
        project_name (str): Project name.
        preset_name (str): Preset name from settings.
        versions_data (list[dict[str, str]]): Per version data.
        sender (str): Sender name.
        identifier (str): Identifier for the delivery batch grouping.
        processing_type (str): Type of processing.

    """

    if not project_name:
        raise ValueError(
            "Project name is required. Got {}".format(str(project_name))
        )

    if not preset_name:
        raise ValueError("Preset name is required.")

    if not versions_data:
        raise ValueError("Got empty versions.")

    for version_data in versions_data:
        version_id = version_data["id"]
        folder_by_version_ids = await get_folder_entity_for_version_ids(
            project_name, [version_data["id"]]
        )
        folder_entity = folder_by_version_ids.get(version_data["id"])

        if not folder_entity:
            raise ValueError(
                "Folder entity not found for version "
                f"{version_data['id']}"
            )

        # Prepare payload data
        payload_data = {
            "processing_type": processing_type,
            "version_data": version_data,
            "folder_data": {
                "id": folder_entity.id,
                "name": folder_entity.name,
                "path": folder_entity.path,
            },
            "preset_name": preset_name,
            "identifier": identifier,
        }
        if representation_data:
            payload_data["representation_data"] = representation_data[
                version_id]

        message, description = create_nice_event_message_and_description(
            "Requesting",
            "Batchdelivery",
            processing_type,
            {
                "project": project_name,
                "sender": sender,
                "payload": payload_data,
                "identifier": identifier,
            },
        )

        # message will be shown in UX
        payload_data["message"] = message

        # await EventStream.dispatch(
        #     OFFLOAD_SRC_TOPIC,
        #     project=project_name,
        #     sender=sender,
        #     user=sender,
        #     description=description,
        #     payload=payload_data,
        # )


async def get_folder_entity_for_version_ids(
    project_name: str, version_ids: list[str]
) -> dict[str, Any]:
    """Helper function for resolving folder entities for given version ids.

    Args:
        project_name (str): Project name.
        version_ids (list[str]): Version ids.

    Returns:
        dict[str, Any]: Folder entities by version ids.

    """
    version_ids = set(version_ids)
    output = {
        version_id: None
        for version_id in version_ids
    }
    if not version_ids:
        return output

    logger.debug(f"Resolving folder entities for versions: {version_ids}")
    product_id_by_version_id = {
        version.id: version.product_id
        for version in await get_versions(
            project_name,
            version_ids=version_ids,
            fields={"id", "productId"}
        )
    }

    product_ids = set(product_id_by_version_id.values())
    if not product_ids:
        return output

    folder_id_by_product_id = {
        product.id: product.folder_id
        for product in await get_products(
            project_name,
            product_ids=product_ids,
            fields={"id", "folderId"}
        )
    }
    folder_ids = set(folder_id_by_product_id.values())
    if not folder_ids:
        return output

    folders_by_id = {
        folder.id: folder
        for folder in await get_folders(
            project_name,
            folder_ids=folder_ids,
        )
    }
    for version_id, product_id in product_id_by_version_id.items():
        folder_id = folder_id_by_product_id.get(product_id)
        if folder_id:
            output[version_id] = folders_by_id.get(folder_id)

    return output


def create_nice_event_message_and_description(
    action_topic: str,
    service: str,
    processing_type: str,
    job_data: dict[str, Any],
) -> tuple[str, str]:
    """Create nice message and description for event.

    Args:
        action_topic (str): Action topic.
        service (str): Service name
        job_data (dict[str, Any]): Job data (usually source event).

    Returns:
        tuple[str, str]: Message and description.
    """
    job_payload = job_data["payload"]
    project_name = job_data["project"]
    job_sender = job_data["sender"]
    identifier = job_payload["identifier"]

    job_id = job_data.get("id", "")

    # check if version_data are in payload if they are get id
    version_id = None
    version_data = job_payload.get("version_data")
    if version_data:
        version_id = version_data["id"]

    # check if `message` is in payload if it is then pop it
    #   and use it as description
    message = job_payload.pop("message", None)
    if not message:
        message = (
            f"{action_topic} | {service} {processing_type} job "
            f"{job_id} for project '{project_name}' "
            f"requested by '{job_sender}'. \n\n"
            f"Identifier: {identifier} \n\n"
            f"Data {json.dumps(job_payload, indent=2)}"
        )

    description = (
        f"{action_topic} | {service} {processing_type} job {job_id} ...")
    if version_id:
        description = (
            f"{action_topic} | {service} {processing_type} job "
            f"for version '{version_id}' ..."
        )

    return message, description
