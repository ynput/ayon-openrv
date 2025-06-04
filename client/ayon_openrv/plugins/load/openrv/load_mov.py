from __future__ import annotations

import rv
import os
from typing import ClassVar, Optional

from ayon_core.pipeline import load
from ayon_openrv.api.ocio import (
    set_group_ocio_active_state,
    set_group_ocio_colorspace
)
from ayon_openrv.api.pipeline import imprint_container


class MovLoader(load.LoaderPlugin):
    """Load mov into OpenRV"""

    label = "Load MOV"
    product_types: ClassVar[set] = {"*"}
    representations: ClassVar[set] = {"*"}
    extensions: ClassVar[set] = {"mov", "mp4"}
    order = 0

    icon = "code-fork"
    color = "orange"

    def load(self, context, name=None, namespace=None, data=None):

        filepath = self.filepath_from_context(context)
        namespace = namespace if namespace else context["folder"]["name"]
        rep_name = os.path.basename(filepath)

        loaded_node = rv.commands.addSourceVerbose([filepath])

        node = self._finalize_loaded_node(
            loaded_node, rep_name, filepath)

        # update colorspace
        self.set_representation_colorspace(node,
                                           context["representation"])

        imprint_container(
            node,
            name=name,
            namespace=namespace,
            context=context,
            loader=self.__class__.__name__
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
            [filepath]
        )
        rv.commands.setActiveSourceMediaRep(
            loaded_node,
            rep_name,
        )
        source_reps = rv.commands.sourceMediaReps(loaded_node)
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
            if (
                node_type == "RVFileSource"
                and source_node_name == ""
            ):
                rv.commands.deleteNode(node_gorup)
            else:
                node = source_node
                break

        rv.commands.setStringProperty(
            f"{node}.media.name", [rep_name], True)

        rv.commands.reload()
        return node

    def update(self, container, context):

        node = container["node"]
        filepath = rv.commands.sequenceOfFile(
            self.filepath_from_context(context))[0]

        repre_entity = context["representation"]

        new_rep_name = os.path.basename(filepath)
        source_reps = rv.commands.sourceMediaReps(node)
        self.log.warning(f">> source_reps: {source_reps}")

        if new_rep_name not in source_reps:
            # change path
            rv.commands.addSourceMediaRep(
                node,
                new_rep_name,
                [filepath]
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
        representation = context["representation"]
        self.set_representation_colorspace(node, representation)

        # update name
        rep_name = rv.commands.getStringProperty(f"{node}.media.name")
        rv.commands.setStringProperty(
            f"{node}.media.name", [new_rep_name], True)
        rv.commands.setStringProperty(
            f"{node}.media.repName", [rep_name], True)
        rv.commands.setStringProperty(
            f"{node}.ayon.representation", [repre_entity["id"]], True)
        rv.commands.reload()

    def remove(self, container):
        node = container["node"]
        # since we are organizing all loaded sources under a switch group
        # we need to remove all the source nodes organized under it
        switch_node = rv.commands.sourceMediaRepSwitchNode(node)
        for node_data in rv.commands.sourceMediaRepsAndNodes(switch_node):
            source_node_name = node_data[0]
            source_node = node_data[1]
            node_type = rv.commands.nodeType(source_node)
            node_group = rv.commands.nodeGroup(source_node)

            if node_type == "RVFileSource":
                self.log.warning(f">> node_type: {node_type}")
                self.log.warning(f">> source_node_name: {source_node_name}")
                rv.commands.deleteNode(node_group)

        rv.commands.reload()

    def set_representation_colorspace(self, node, representation):
        colorspace_data = representation.get("data", {}).get("colorspaceData")
        if colorspace_data:
            colorspace = colorspace_data["colorspace"]
            # TODO: Confirm colorspace is valid in current OCIO config
            #   otherwise errors will be spammed from OpenRV for invalid space

            self.log.info(f"Setting colorspace: {colorspace}")
            group = rv.commands.nodeGroup(node)

            # Enable OCIO for the node and set the colorspace
            set_group_ocio_active_state(group, state=True)
            set_group_ocio_colorspace(group, colorspace)
