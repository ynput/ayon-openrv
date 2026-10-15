from __future__ import annotations

import os
import json
import collections
from typing import Any

from ayon_applications import ApplicationManager

from ayon_core.lib.transcoding import (
    IMAGE_EXTENSIONS, VIDEO_EXTENSIONS
)
from ayon_core.pipeline.actions import (
    LoaderActionItem,
    LoaderActionPlugin,
    LoaderActionResult,
    LoaderActionSelection,
)

from ayon_openrv.networking import RVConnector


SUPPORTED_EXTENSIONS = {
    ext.lower()
    for ext in IMAGE_EXTENSIONS | VIDEO_EXTENSIONS
}


class _BasePlayInRVAction(LoaderActionPlugin):
    """Base for actions sending representations to network connected OpenRV.

    Could be run from Loader in DCC or outside.
    """
    skip_discovery = True

    label = None
    order = -10
    icon = {
        "type": "material-symbols",
        "name": "play_circle",
        "color": "#FFA500",
    }

    def get_action_items(
        self, selection: LoaderActionSelection
    ) -> list[LoaderActionItem]:
        repre_ids_by_name = collections.defaultdict(set)
        for repre in self._get_selected_representations(selection):
            if self._is_supported_representation(repre):
                repre_ids_by_name[repre["name"]].add(repre["id"])

        return [
            LoaderActionItem(
                label=repre_name,
                group_label=self.label,
                order=self.order,
                data={"representation_ids": list(repre_ids)},
                icon=self.icon,
            )
            for repre_name, repre_ids in repre_ids_by_name.items()
        ]

    def execute_action(
        self,
        selection: LoaderActionSelection,
        data: dict[str, Any],
        form_values: dict[str, Any],
    ) -> LoaderActionResult | None:
        repre_ids = data.get("representation_ids")
        if not repre_ids:
            return LoaderActionResult(
                "Missing representation ids.",
                success=False,
            )

        repre_entities = selection.entities.get_representations(
            set(repre_ids)
        )
        if not repre_entities:
            return LoaderActionResult(
                "Failed to find representations in AYON.",
                success=False,
            )

        rv_connector = RVConnector()
        if not rv_connector.is_connected:
            result = self._handle_not_connected(selection, repre_entities)
            if result is not None:
                return result

        payload = json.dumps([
            {
                "objectName": repre_entity["name"],
                "representation": repre_entity["id"],
            }
            for repre_entity in repre_entities
        ])
        # This also retries the connection
        with rv_connector:
            rv_connector.send_event(
                "ayon_load_container",
                payload,
                shall_return=False
            )

        return LoaderActionResult("Sent to OpenRV.", success=True)

    def _handle_not_connected(
        self,
        selection: LoaderActionSelection,
        repre_entities: list[dict[str, Any]],
    ) -> LoaderActionResult | None:
        """Handle missing connection to OpenRV.

        Returns:
            LoaderActionResult | None: Result to return from the action
                or 'None' to continue with sending the representations.

        """
        raise NotImplementedError

    def _get_selected_representations(
        self, selection: LoaderActionSelection
    ) -> list[dict[str, Any]]:
        if selection.selected_type == "representation":
            return selection.entities.get_representations(
                selection.selected_ids
            )
        if selection.selected_type == "version":
            return selection.entities.get_versions_representations(
                selection.selected_ids
            )
        return []

    def _is_supported_representation(self, repre: dict[str, Any]) -> bool:
        repre_context = repre.get("context") or {}
        ext = repre_context.get("ext")
        if not ext:
            path = repre["attrib"].get("path")
            if path:
                ext = os.path.splitext(path)[1]

        if not ext:
            return False

        ext = ext.lower()
        if not ext.startswith("."):
            ext = f".{ext}"
        return ext in SUPPORTED_EXTENSIONS


class PlayInRVAction(_BasePlayInRVAction):
    """Open representations in OpenRV, launch OpenRV if is not running.

    It expects to be run only on representations published to any task!
    """
    identifier = "openrv.play-in-rv"
    label = "Open in RV"

    def _handle_not_connected(
        self,
        selection: LoaderActionSelection,
        repre_entities: list[dict[str, Any]],
    ) -> LoaderActionResult | None:
        # get launch context variables
        project_name = selection.project_name
        folder_path, task_name = self._get_launch_context(
            selection, repre_entities[0]
        )
        if not folder_path:
            return LoaderActionResult(
                "Selected representation does not have available folder."
                " It is not possible to start OpenRV.",
                success=False,
            )

        # launch RV with context
        app_manager = ApplicationManager()
        openrv_app = app_manager.find_latest_available_variant_for_group(
            "openrv"
        )
        if not openrv_app:
            return LoaderActionResult(
                "No configured OpenRV found in"
                " Applications. Ask admin to configure it"
                " in ayon+settings://applications/applications/openrv.",
                success=False,
            )
        openrv_app.launch(
            project_name=project_name,
            folder_path=folder_path,
            task_name=task_name,
            # Enforce the `-network` argument so that RV allows receiving
            # the event we will send it. Note that passing `-network`
            # multiple times seems fine, so if app arguments or a
            # pre-launch hook may be enforcing it as well it should not
            # cause any issues.
            app_args=["-network"],
        )
        return None

    def _get_launch_context(
        self,
        selection: LoaderActionSelection,
        repre_entity: dict[str, Any],
    ) -> tuple[str | None, str | None]:
        version_id = repre_entity["versionId"]
        products = selection.entities.get_versions_products({version_id})
        folders = selection.entities.get_products_folders(
            {product["id"] for product in products}
        )
        if not folders:
            return None, None
        folder_entity = folders[0]
        folder_path = folder_entity.get("path")

        # could be published without task from Publisher
        tasks = selection.entities.get_versions_tasks({version_id})
        task_name = None
        if tasks:
            task_name = tasks[0]["name"]

        if not task_name:
            repre_context = repre_entity.get("context") or {}
            task_info = repre_context.get("task")
            if isinstance(task_info, str):
                task_name = task_info
            elif isinstance(task_info, dict):
                task_name = task_info.get("name")

            if task_name:
                # Validate the task exists on the folder
                folder_task_names = {
                    task["name"]
                    for task in selection.entities.get_folders_tasks(
                        {folder_entity["id"]}
                    )
                }
                if task_name not in folder_task_names:
                    task_name = None

        return folder_path, task_name


class PlayInExistingRVAction(_BasePlayInRVAction):
    """Open representations in already running network connected OpenRV."""
    identifier = "openrv.play-in-existing-rv"
    label = "Open in Existing RV"

    def _handle_not_connected(
        self,
        selection: LoaderActionSelection,
        repre_entities: list[dict[str, Any]],
    ) -> LoaderActionResult | None:
        return LoaderActionResult(
            "No existing OpenRV connection found."
            " Make sure OpenRV is running and network connected.",
            success=False,
        )
