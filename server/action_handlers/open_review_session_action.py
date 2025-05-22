from pprint import pformat
import time
from ayon_server.actions import (
    ActionExecutor,
    ExecuteResponseModel,
    SimpleActionManifest,
)

from ayon_server.addons import BaseServerAddon
from ayon_server.forms import SimpleForm
from ayon_server.logging import logger

# Import the batchdelivery common functions
from .lib import (
    request_offloaded_process,
    prepare_delivery_version_data
)

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
    allow_multiselection=True,
)

async def handler_open_review_session(
    addon: BaseServerAddon,
    executor: ActionExecutor,
) -> ExecuteResponseModel:
    """
    Handles the delivery action form flow.

    This action allows users to select a delivery preset and
    submit selected versions for delivery processing.
    """
    # Get the action context and project name
    context = executor.context
    project_name = context.project_name
    user_name = executor.user.name
    settings_variant = executor.variant
    logger.info(pformat(settings_variant))

    # Get the form data if it exists
    form_data = context.form_data or {}

    # Check where we are in the flow
    step = form_data.get("step", "select_version_representations")

    #
    if step == "failed":
        return await executor.get_server_action_response(
            success=False
        )

    if step == "select_version_representations":

        # Build the form to select a preset
        form = SimpleForm()
        form.label("Select version represetations")

        form.hidden("step", "select_app_openrv_variant")

        return await executor.get_server_action_response(
            message="Select version representations",
            form=form
        )

    elif step == "select_app_openrv_variant":

        # Build the form to select a preset
        form = SimpleForm()
        form.label("Select OpenRV variant")

        form.hidden("step", "open_session_in_variant")

        return await executor.get_server_action_response(
            message="Select OpenRV variant",
            form=form
        )


    elif step == "open_session_in_variant":

        return await executor.get_server_action_response(
            message="Opening session in OpenRV",
        )

    # If we get here, something went wrong
    return await executor.get_server_action_response(
        message="Something went wrong",
        success=False
    )
