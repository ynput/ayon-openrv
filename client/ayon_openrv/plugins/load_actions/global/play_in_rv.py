from __future__ import annotations

import os
import json
import collections
from typing import Any

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
    """Base for actions opening representations in OpenRV.

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

    def _get_representations(
        self,
        selection: LoaderActionSelection,
        data: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Representation entities of an action item.

        Returns an empty list when the item data is not usable or when the
        representations cannot be found anymore.

        """
        repre_ids = data.get("representation_ids") if data else None
        if not repre_ids:
            return []
        return selection.entities.get_representations(set(repre_ids))

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
    """Open representations in a new OpenRV instance.

    A new instance is always started, on a network port no other session
    uses, even when an OpenRV session is already running. Use 'Open in
    Existing RV' to add representations to the running session.
    """
    identifier = "openrv.play-in-rv"
    label = "Open in RV"

    def execute_action(
        self,
        selection: LoaderActionSelection,
        data: dict[str, Any],
        form_values: dict[str, Any],
    ) -> LoaderActionResult | None:
        addon = self._context.get_addons_manager().get("openrv")
        if addon is None:
            return LoaderActionResult(
                "OpenRV is not available in the current AYON bundle.",
                success=False,
            )

        repre_entities = self._get_representations(selection, data)
        if not repre_entities:
            return LoaderActionResult(
                "Failed to find representations in AYON.",
                success=False,
            )

        try:
            addon.open_representations_in_new_rv(
                selection.project_name, repre_entities
            )
        except Exception as error:
            self.log.warning(
                "Failed to open representations in a new OpenRV instance.",
                exc_info=True,
            )
            return LoaderActionResult(str(error), success=False)

        return LoaderActionResult(
            "Opened in a new OpenRV instance.", success=True
        )


class PlayInExistingRVAction(_BasePlayInRVAction):
    """Open representations in already running network connected OpenRV."""
    identifier = "openrv.play-in-existing-rv"
    label = "Open in Existing RV"

    def execute_action(
        self,
        selection: LoaderActionSelection,
        data: dict[str, Any],
        form_values: dict[str, Any],
    ) -> LoaderActionResult | None:
        repre_entities = self._get_representations(selection, data)
        if not repre_entities:
            return LoaderActionResult(
                "Failed to find representations in AYON.",
                success=False,
            )

        rv_connector = RVConnector()
        if not rv_connector.is_connected:
            return LoaderActionResult(
                "No existing OpenRV connection found."
                " Make sure OpenRV is running and network connected.",
                success=False,
            )

        # The project is sent with the event: the running session can be in
        # another project than the representations come from.
        payload = json.dumps([
            {
                "objectName": repre_entity["name"],
                "representation": repre_entity["id"],
                "project_name": selection.project_name,
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
