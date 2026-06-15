import os
from typing import Any, Optional

from ayon_core.pipeline.actions import (
    LoaderActionItem,
    LoaderActionPlugin,
    LoaderActionResult,
    LoaderActionSelection,
)
from ayon_core.pipeline.load import get_representation_path_with_anatomy
from ayon_core.pipeline import registered_host

import rv.commands


class OpenRVSessionAction(LoaderActionPlugin):
    """Open selected RV representation as an RV session."""

    identifier = "openrv.open-rv-session"

    def get_action_items(
        self,
        selection: LoaderActionSelection,
    ) -> list[LoaderActionItem]:
        items = []
        for representation in self._get_selected_representations(selection):
            if representation["name"].lower() != "rv":
                continue

            items.append(
                LoaderActionItem(
                    label="Open RV session",
                    order=0,
                    data={"representation_id": representation["id"]},
                    icon={
                        "type": "material-symbols",
                        "name": "live_tv",
                        "color": "#FFA500",
                    },
                )
            )
        return items

    def execute_action(
        self,
        selection: LoaderActionSelection,
        data: dict[str, Any],
        form_values: dict[str, Any],
    ) -> Optional[LoaderActionResult]:
        representation_id = data.get("representation_id")
        if not representation_id:
            return LoaderActionResult(
                "Missing representation id.",
                success=False,
            )

        representation = next(
            iter(selection.entities.get_representations({representation_id})),
            None,
        )
        if not representation:
            return LoaderActionResult(
                "Failed to find representation in AYON.",
                success=False,
            )

        workfile_path = get_representation_path_with_anatomy(
            representation,
            selection.project_anatomy,
        )
        if not workfile_path:
            return LoaderActionResult(
                "Failed to resolve representation path.",
                success=False,
            )
        if not os.path.exists(workfile_path):
            return LoaderActionResult(
                f"RV session file was not found: {workfile_path}",
                success=False,
            )

        # Open workfile
        host = registered_host()
        host.open_workfile(workfile_path)
        # Unset session to avoid user saving into it
        rv.commands.setSessionFileName("")

        return LoaderActionResult("Opened RV session in OpenRV.", success=True)

    def _get_selected_representations(
        self,
        selection: LoaderActionSelection,
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

