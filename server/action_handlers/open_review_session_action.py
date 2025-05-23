from pprint import pformat
import re
from ayon_server.actions import (
    ActionExecutor,
    ExecuteResponseModel,
    SimpleActionManifest,
)

from ayon_server.lib.postgres import Postgres
from ayon_server.forms.simple_form import FormSelectOption
from ayon_server.entity_lists import EntityList
from ayon_server.helpers.get_entity_class import get_entity_class
from ayon_server.addons import BaseServerAddon
from ayon_server.forms import SimpleForm
from ayon_server.logging import logger

async def get_version_representations(
        project_name: str,
        version_ids: list[str],
) -> dict[str, dict[str, dict]]:
    result: dict[str, dict[str, dict]] = {}
    async with Postgres.acquire() as conn, conn.transaction():
        query = f"""
        SELECT id, version_id, name, data
        FROM project_{project_name}.representations
        WHERE version_id = any($1)
        """
        repre_data = {}
        async for row in Postgres.iterate(query, version_ids):
            logger.info(f"Processing version {row}")
            if row["version_id"] not in result:
                repre_data = {
                    row["id"]: {
                        "name": row["name"],
                        "data": row["data"],
                    },
                }
                result[row["version_id"]] = repre_data
            else:
                repre_data[row["id"]] = {
                    "name": row["name"],
                    "data": row["data"],
                }
    return result

ENTRYPOINT = SimpleActionManifest(
    identifier="openrv-run-review-session",
    label="Open in OpenRV",
    category="Review",
    order=99,
    icon={"type": "url", "url": "{addon_url}/public/icons/review-sesison.png"},
    entity_type="list",
    entity_subtypes=[
        "version:review-session",
        "version:generic",
    ],
    allow_multiselection=False,
)

async def handler_open_review_session(
    addon: BaseServerAddon,
    executor: ActionExecutor,
) -> ExecuteResponseModel:
    """
    Handles the OpenRV review session opening action form flow.

    This function is called from Reviwe session lists or from Generic
    version lists.
    """
    # Get the action context and project name
    context = executor.context
    list_id = context.entity_ids[0]
    project_name = context.project_name
    user_name = executor.user.name
    settings_variant = executor.variant
    logger.info(pformat(executor.context))

    # Get the form data if it exists
    form_data = context.form_data or {}

    # Load list entity and prepare basic data (needed for most steps)
    list_entity = await EntityList.load(project_name, list_id)

    if not list_entity:
        return await executor.get_server_action_response(
            message="List cannot be found or is not available.",
            success=False,
        )

    # Aggregate all version ids into folder_path related lists under one dictionary
    folder_path_versions = {}
    version_to_folder = {}  # Create a reverse mapping for quick lookups
    all_version_ids = []

    for item in list_entity.items:
        folder_path = item.folder_path
        entity_id = item.entity_id

        if folder_path not in folder_path_versions:
            folder_path_versions[folder_path] = []

        folder_path_versions[folder_path].append(entity_id)
        version_to_folder[entity_id] = folder_path  # Store direct mapping
        all_version_ids.append(entity_id)

    logger.info(f"Folder version IDs: {pformat(folder_path_versions)}")
    logger.info(f"List version IDs: {pformat(all_version_ids)}")

    if not all_version_ids:
        return await executor.get_server_action_response(
            message="No versions in list.",
            success=False,
        )

    # Check where we are in the flow
    step = form_data.get("step", "select_version_representations")

    if step == "failed":
        return await executor.get_server_action_response(
            success=False,
        )

    if step == "select_version_representations":
        representations = await get_version_representations(
            project_name, all_version_ids,
        )

        # Get default representation settings from addon settings
        project_settings = await addon.get_project_settings(
            project_name, settings_variant)

        # get attr by path
        # actions/handler_open_review_session/default_representation
        default_representation_patterns = getattr(
            project_settings.actions.handler_open_review_session,
            "default_representation",
            [],
        )
        logger.info(
            f"Default representation patterns: "
            f"{pformat(default_representation_patterns)}"
        )

        # Build the form to select representations
        form = SimpleForm()
        form.label("Select version representations")

        # Create representation selection for each version, sorted by folder path
        for folder_path in sorted(folder_path_versions.keys()):
            for version_id in folder_path_versions[folder_path]:
                repre_options = representations.get(version_id, {})
                if not repre_options:
                    continue
            # generate all FormOptions
            repre_select_options = []
            version_select_label = None
            default_repre_id = None

            for repre_id, repre_data in repre_options.items():
                repre_name = repre_data["name"]
                repre_option = FormSelectOption(
                    label=repre_name,
                    value=repre_id,
                )
                repre_select_options.append(repre_option)

                # Set version label if not already set
                if not version_select_label:
                    version_select_label = (
                        f"{repre_data['data']['context']['folder']['name']} "
                        f"{repre_data['data']['context']['product']['name']} "
                        f"v{repre_data['data']['context']['version']}"
                    )

                # Check if this representation matches any pattern in settings
                if (default_repre_id is None and
                    default_representation_patterns):
                    for pattern in default_representation_patterns:
                        if re.search(pattern, repre_name):
                            default_repre_id = repre_id
                            break

            if repre_select_options:
                form.select(
                    name=version_id,
                    options=repre_select_options,
                    label=version_select_label,
                    value=default_repre_id,
                )

        form.hidden("step", "select_app_openrv_variant")
        form.hidden("representations", representations)
        form.hidden("all_version_ids", all_version_ids)
        form.hidden("folder_path_versions", folder_path_versions)
        form.hidden("version_to_folder", version_to_folder)

        return await executor.get_server_action_response(
            message="Select version representations",
            form=form,
        )

    elif step == "select_app_openrv_variant":
        # Get data from previous step
        representations = form_data["representations"]
        all_version_ids = form_data["all_version_ids"]
        folder_path_versions = form_data["folder_path_versions"]
        version_to_folder = form_data["version_to_folder"]

        # Validate that representations were selected
        repre_data = {}
        for version_id in [v for v in all_version_ids]:
            repre_id = form_data.get(version_id)
            if not repre_id:
                form = SimpleForm()
                form.label(
                    "Error: Missing selected representation.",
                    highlight="error")
                form.hidden("step", "failed")
                return await executor.get_server_action_response(
                    form=form,
                    success=True,
                )
            _repres_data = representations.get(version_id)
            if repre_id:
                # Direct lookup of folder_path using the mapping
                folder_path = version_to_folder.get(version_id)

                repre_data[version_id] = {
                    "id": repre_id,
                    "name": _repres_data[repre_id]["name"],
                    "folder_path": folder_path,
                }
        logger.info(
            f"Selected representations: {pformat(repre_data)}"
        )
        # Build the form to select a preset
        form = SimpleForm()
        form.label("Select OpenRV variant")

        form.hidden("step", "open_session_in_variant")
        form.hidden("representations", representations)
        form.hidden("all_version_ids", all_version_ids)
        form.hidden("repre_data", repre_data)

        return await executor.get_server_action_response(
            message="Select OpenRV variant",
            form=form,
        )


    elif step == "open_session_in_variant":
        # Get data from previous steps
        representations = form_data.get("representations", {})
        all_version_ids = form_data.get("all_version_ids", [])
        repre_data = form_data.get("repre_data", {})

        # Here you would process the selected representations
        # and open them in OpenRV with the selected variant

        return await executor.get_server_action_response(
            message=f"Opening {len(repre_data)} representations in OpenRV",
            success=True,
        )

    # If we get here, something went wrong
    return await executor.get_server_action_response(
        message="Something went wrong",
        success=False,
    )
