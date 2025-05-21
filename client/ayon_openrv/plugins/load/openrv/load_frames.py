"""Loader for image sequences and single frames in OpenRV."""
from __future__ import annotations

from typing import ClassVar, Optional

import rv
from ayon_core.lib.transcoding import IMAGE_EXTENSIONS
from ayon_core.pipeline import load
from ayon_openrv.api.ocio import (
    set_group_ocio_active_state,
    set_group_ocio_colorspace,
)
from ayon_openrv.api.pipeline import imprint_container


class FramesLoader(load.LoaderPlugin):
    """Load frames into OpenRV."""

    label = "Load Frames"
    product_types: ClassVar[set] = {"*"}
    representations: ClassVar[set] = {"*"}
    extensions: ClassVar[set] = {ext.lstrip(".") for ext in IMAGE_EXTENSIONS}
    order = 0

    icon = "code-fork"
    color = "orange"

    def load(self,
             context: dict,
             name: Optional[str] = None,
             namespace: Optional[str] = None,
             options: Optional[dict] = None) -> None:
        """Load the frames into OpenRV."""
        sequence = rv.commands.sequenceOfFile(
            self.filepath_from_context(context))

        namespace = namespace or context["folder"]["name"]

        loaded_node = rv.commands.addSourceVerbose([sequence[0]])

        # update colorspace
        self.set_representation_colorspace(loaded_node,
                                           context["representation"])

        imprint_container(
            loaded_node,
            name=name,
            namespace=namespace,
            context=context,
            loader=self.__class__.__name__
        )

    def update(self, container: dict, context: dict) -> None:
        """Update loaded container."""
        node = container["node"]

        filepath = rv.commands.sequenceOfFile(
            self.filepath_from_context(context))[0]

        repre_entity = context["representation"]

        # change path
        rv.commands.setSourceMedia(node, [filepath])

        # update colorspace
        self.set_representation_colorspace(node, context["representation"])

        # update name
        rv.commands.setStringProperty(
            f"{node}.media.name", ["newname"], allowResize=True)
        rv.commands.setStringProperty(
            f"{node}.media.repName", ["repname"], allowResize=True)
        rv.commands.setStringProperty(
            f"{node}.ayon.representation",
            [repre_entity["id"]], allowResize=True
        )

    def remove(self, container: dict) -> None:  # noqa: PLR6301
        """Remove loaded container."""
        node = container["node"]
        group = rv.commands.nodeGroup(node)
        rv.commands.deleteNode(group)

    @staticmethod
    def set_representation_colorspace(node: str, representation: dict) -> None:
        """Set colorspace based on representation data."""
        colorspace_data = representation.get("data", {}).get("colorspaceData")
        if colorspace_data:
            colorspace = colorspace_data["colorspace"]
            # TODO: Confirm colorspace is valid in current OCIO config
            #   otherwise errors will be spammed from OpenRV for invalid space

            group = rv.commands.nodeGroup(node)

            # Enable OCIO for the node and set the colorspace
            set_group_ocio_active_state(group, state=True)
            set_group_ocio_colorspace(group, colorspace)
