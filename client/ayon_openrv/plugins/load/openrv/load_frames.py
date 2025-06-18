"""Loader for image sequences and single frames in OpenRV."""

from __future__ import annotations

import os
from typing import ClassVar

from ayon_core.lib.transcoding import IMAGE_EXTENSIONS
from ayon_core.pipeline import load
from ayon_openrv.api.ocio import (
    set_group_ocio_active_state,
    set_group_ocio_colorspace,
)
from ayon_openrv.api.pipeline import imprint_container

import rv


class FramesLoader(load.LoaderPlugin):
    """Load frames into OpenRV."""

    label = "Load Frames"
    product_types: ClassVar[set] = {"*"}
    representations: ClassVar[set] = {"*"}
    extensions: ClassVar[set] = {ext.lstrip(".") for ext in IMAGE_EXTENSIONS}
    order = 0

    icon = "code-fork"
    color = "orange"

    def load(
        self,
        context: dict,
        name: str | None = None,
        namespace: str | None = None,
        options: dict | None = None,
    ) -> None:
        """Load the frames into OpenRV."""
        filepath = rv.commands.sequenceOfFile(
            self.filepath_from_context(context),
        )[0]

        rep_name = os.path.basename(filepath)

        # change path
        namespace = namespace or context["folder"]["name"]
        loaded_node = rv.commands.addSourceVerbose([filepath])

        node = self._finalize_loaded_node(loaded_node, rep_name, filepath)

        # update colorspace
        self.set_representation_colorspace(node, context["representation"])

        imprint_container(
            node,
            name=name,
            namespace=namespace,
            context=context,
            loader=self.__class__.__name__,
        )

    def _finalize_loaded_node(self, loaded_node, rep_name, filepath):
        """Finalize the loaded node in OpenRV.

        We are organizing all loaded sources under a switch group so we can
        let user switch between versions later on. Every new updated verion is
        added as new media representation under the switch group.

        We are removing firstly added source since it does not have a name.

        Args:
            loaded_node (str): The node that was loaded.
            rep_name (str): The name of the representation.
            filepath (str): The path of the representation.

        Returns:
            str: The node that was loaded.

        """
        node = loaded_node

        rv.commands.addSourceMediaRep(
            loaded_node,
            rep_name,
            [filepath],
        )
        rv.commands.setActiveSourceMediaRep(
            loaded_node,
            rep_name,
        )
        switch_node = rv.commands.sourceMediaRepSwitchNode(loaded_node)
        node_type = rv.commands.nodeType(switch_node)

        for node in rv.commands.sourceMediaRepsAndNodes(switch_node):
            source_node_name = node[0]
            source_node = node[1]
            node_type = rv.commands.nodeType(source_node)
            node_gorup = rv.commands.nodeGroup(source_node)

            # we are removing the firstly added wource since it does not have
            # a name and we don't want to confuse the user with multiple
            # versions of the same source but one of them without a name
            if node_type == "RVFileSource" and source_node_name == "":
                rv.commands.deleteNode(node_gorup)
            else:
                node = source_node
                break

        rv.commands.setStringProperty(f"{node}.media.name", [rep_name], True)

        rv.commands.reload()
        return node

    def update(self, container: dict, context: dict) -> None:
        """Update loaded container."""
        node = container["node"]
        filepath = rv.commands.sequenceOfFile(
            self.filepath_from_context(context),
        )[0]

        repre_entity = context["representation"]

        new_rep_name = os.path.basename(filepath)
        source_reps = rv.commands.sourceMediaReps(node)
        self.log.warning(f">> source_reps: {source_reps}")

        if new_rep_name not in source_reps:
            # change path
            rv.commands.addSourceMediaRep(
                node,
                new_rep_name,
                [filepath],
            )
        else:
            self.log.warning(">> new_rep_name already in source_reps")

        rv.commands.setActiveSourceMediaRep(
            node,
            new_rep_name,
        )
        source_rep_name = rv.commands.sourceMediaRep(node)
        self.log.info(f"New source_rep_name: {source_rep_name}")

        # update colorspace
        self.set_representation_colorspace(node, context["representation"])

        # add data for inventory manager
        rv.commands.setStringProperty(
            f"{node}.ayon.representation",
            [repre_entity["id"]],
            True,
        )
        rv.commands.reload()

    def remove(self, container: dict) -> None:  # noqa: PLR6301
        """Remove loaded container."""
        node = container["node"]
        # since we are organizing all loaded sources under a switch group
        # we need to remove all the source nodes organized under it
        switch_node = rv.commands.sourceMediaRepSwitchNode(node)
        if not switch_node:
            # just in case someone removed it maunally
            return

        for node in rv.commands.sourceMediaRepsAndNodes(switch_node):
            source_node_name = node[0]
            source_node = node[1]
            node_type = rv.commands.nodeType(source_node)
            node_group = rv.commands.nodeGroup(source_node)

            if node_type == "RVFileSource":
                self.log.info(f"Removing: {source_node_name}")
                rv.commands.deleteNode(node_group)

        rv.commands.reload()
        # switch node is child of some other node. find its parent node
        parent_node = rv.commands.nodeGroup(switch_node)
        if parent_node:
            self.log.info(f"Removing: {parent_node}")
            rv.commands.deleteNode(parent_node)

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

    def switch(self, container, context):
        self.update(container, context)
