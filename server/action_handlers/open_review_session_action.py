from __future__ import annotations
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
from ayon_server.addons import BaseServerAddon
from ayon_server.forms import SimpleForm
from ayon_server.logging import logger


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


class OpenReviewSessionHandler:
    """Handler for OpenRV review session actions."""

    def __init__(self, addon: BaseServerAddon, executor: ActionExecutor):
        self.addon = addon
        self.executor = executor
        self.context = executor.context
        self.project_name = self.context.project_name
        self.user_name = executor.user.name
        self.settings_variant = executor.variant
        self.form_data = self.context.form_data or {}
        self.list_entity = None
        self.all_version_ids = []
        self.folder_path_versions = {}
        self.version_to_folder = {}

    async def _load_list_entity(self) -> bool:
        """Load list entity and prepare data structures.

        Returns:
            bool: True if list entity was loaded successfully, False otherwise.
        """
        list_id = self.context.entity_ids[0]
        self.list_entity = await EntityList.load(self.project_name, list_id)

        if not self.list_entity:
            return False

        # Build version mappings once
        self._build_version_mappings()
        return True

    def _build_version_mappings(self) -> None:
        """Build version mappings for folder paths and versions."""
        for item in self.list_entity.items:
            folder_path = item.folder_path
            entity_id = item.entity_id

            if folder_path not in self.folder_path_versions:
                self.folder_path_versions[folder_path] = []

            self.folder_path_versions[folder_path].append(entity_id)
            self.version_to_folder[entity_id] = folder_path
            self.all_version_ids.append(entity_id)

        logger.info(
            f"Folder version IDs: {pformat(self.folder_path_versions)}")
        logger.info(
            f"list version IDs: {pformat(self.all_version_ids)}")

    async def _get_version_representations(self) -> dict[str, dict[str, dict]]:
        """Get representations for all versions.

        Returns:
            dict[str, dict[str, dict]]: Mapping of version_id to
                representation data.
        """
        result: dict[str, dict[str, dict]] = {}
        async with Postgres.acquire() as conn, conn.transaction():
            query = f"""
            SELECT id, version_id, name, data
            FROM project_{self.project_name}.representations
            WHERE version_id = any($1)
            """
            async for row in Postgres.iterate(query, self.all_version_ids):
                version_id = row["version_id"]
                repre_id = row["id"]

                if version_id not in result:
                    result[version_id] = {}

                result[version_id][repre_id] = {
                    "name": row["name"],
                    "data": row["data"],
                }
        return result

    async def _get_default_representation_patterns(self) -> list[str]:
        """Get default representation patterns from addon settings.

        Returns:
            list[str]: list of regex patterns for default representations.
        """
        project_settings = await self.addon.get_project_settings(
            self.project_name, self.settings_variant)

        return getattr(
            project_settings.actions.handler_open_review_session,
            "default_representation",
            [],
        )

    def _find_default_representation(
        self, repre_options: dict[str, dict], patterns: list[str]
    ) -> str | None:
        """Find default representation based on patterns.

        Args:
            repre_options: dict of representation options
            patterns: list of regex patterns

        Returns:
            str | None: ID of default representation or None
        """
        if not patterns:
            return None

        for repre_id, repre_data in repre_options.items():
            repre_name = repre_data["name"]
            for pattern in patterns:
                if re.search(pattern, repre_name):
                    return repre_id
        return None

    def _get_version_select_label(self, repre_data: dict) -> str:
        """Generate selection label for version.

        Args:
            repre_data: Representation data

        Returns:
            str: Formatted label for version selection
        """
        context = repre_data["data"]["context"]
        return (
            f"{context['folder']['name']} "
            f"{context['product']['name']} "
            f"v{context['version']}"
        )

    async def handle_select_version_representations(
            self) -> ExecuteResponseModel:
        """Handle step for selecting version representations."""
        representations = await self._get_version_representations()
        patterns = await self._get_default_representation_patterns()

        logger.info(f"Default representation patterns: {pformat(patterns)}")

        form = SimpleForm()
        form.label("Select version representations")

        # Create representation selection for each version, sorted by folder
        # path
        for folder_path in sorted(self.folder_path_versions.keys()):
            for version_id in self.folder_path_versions[folder_path]:
                repre_options = representations.get(version_id, {})
                if not repre_options:
                    continue

                # Generate selection options
                repre_select_options = []
                version_select_label = None
                default_repre_id = self._find_default_representation(
                    repre_options, patterns)

                for repre_id, repre_data in repre_options.items():
                    repre_name = repre_data["name"]
                    repre_select_options.append(FormSelectOption(
                        label=repre_name,
                        value=repre_id,
                    ))

                    # Set version label if not already set
                    if not version_select_label:
                        version_select_label = self._get_version_select_label(
                            repre_data)

                if repre_select_options:
                    form.select(
                        name=version_id,
                        options=repre_select_options,
                        label=version_select_label,
                        value=default_repre_id,
                    )

        # Only pass necessary data to next step
        form.hidden("step", "select_app_openrv_variant")
        form.hidden("representations", representations)

        # We don't need to pass these as they'll be rebuilt in next step
        # form.hidden("all_version_ids", self.all_version_ids)
        # form.hidden("folder_path_versions", self.folder_path_versions)
        # form.hidden("version_to_folder", self.version_to_folder)

        return await self.executor.get_server_action_response(
            message="Select version representations",
            form=form,
        )

    async def handle_select_app_openrv_variant(self) -> ExecuteResponseModel:
        """Handle step for selecting OpenRV variant."""
        # Get data from previous step
        representations = self.form_data["representations"]

        # Validate that representations were selected and build repre_data
        repre_data = {}
        for version_id in self.all_version_ids:
            repre_id = self.form_data.get(version_id)
            if not repre_id:
                form = SimpleForm()
                form.label(
                    "Error: Missing selected representation.",
                    highlight="error")
                form.hidden("step", "failed")
                return await self.executor.get_server_action_response(
                    form=form,
                    success=True,
                )

            _repres_data = representations.get(version_id)
            if repre_id and _repres_data:
                # Direct lookup of folder_path using the mapping
                folder_path = self.version_to_folder.get(version_id)

                repre_data[version_id] = {
                    "id": repre_id,
                    "name": _repres_data[repre_id]["name"],
                    "folder_path": folder_path,
                }

        logger.info(f"Selected representations: {pformat(repre_data)}")

        # Build the form to select a preset
        form = SimpleForm()
        form.label("Select OpenRV variant")

        # Only pass necessary data to next step
        form.hidden("step", "open_session_in_variant")
        form.hidden("repre_data", repre_data)

        return await self.executor.get_server_action_response(
            message="Select OpenRV variant",
            form=form,
        )

    async def handle_open_session_in_variant(self) -> ExecuteResponseModel:
        """Handle step for opening session in variant."""
        # Get data from previous step
        repre_data = self.form_data.get("repre_data", {})

        # Here you would process the selected representations
        # and open them in OpenRV with the selected variant

        return await self.executor.get_server_action_response(
            message=f"Opening {len(repre_data)} representations in OpenRV",
            success=True,
        )

    async def handle_failed(self) -> ExecuteResponseModel:
        """Handle failed step."""
        return await self.executor.get_server_action_response(
            success=False,
        )

    async def execute(self) -> ExecuteResponseModel:
        """Main execution method that orchestrates the workflow."""
        # Load list entity and prepare data
        if not await self._load_list_entity():
            return await self.executor.get_server_action_response(
                message="list cannot be found or is not available.",
                success=False,
            )

        # Check if we have any versions
        if not self.all_version_ids:
            return await self.executor.get_server_action_response(
                message="No versions in list.",
                success=False,
            )

        # Handle the current step
        step = self.form_data.get("step", "select_version_representations")

        if step == "failed":
            return await self.handle_failed()
        elif step == "select_version_representations":
            return await self.handle_select_version_representations()
        elif step == "select_app_openrv_variant":
            return await self.handle_select_app_openrv_variant()
        elif step == "open_session_in_variant":
            return await self.handle_open_session_in_variant()

        # If we get here, something went wrong
        return await self.executor.get_server_action_response(
            message="Something went wrong",
            success=False,
        )


async def handler_open_review_session(
    addon: BaseServerAddon,
    executor: ActionExecutor,
) -> ExecuteResponseModel:
    """
    Handles the OpenRV review session opening action form flow.

    This function is called from Review session lists or from Generic
    version lists.
    """
    handler = OpenReviewSessionHandler(addon, executor)
    return await handler.execute()
