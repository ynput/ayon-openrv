from ayon_core.pipeline import load
from ayon_openrv.api.pipeline import imprint_container
from ayon_openrv.api.ocio import (
    set_group_ocio_active_state,
    set_group_ocio_colorspace
)

import rv


class MovLoader(load.LoaderPlugin):
    """Load mov into OpenRV"""

    label = "Load MOV"
    product_types = {"*"}
    representations = {"*"}
    extensions = {"mov", "mp4"}
    order = 0

    icon = "code-fork"
    color = "orange"

    def load(self, context, name=None, namespace=None, data=None):

        filepath = self.filepath_from_context(context)
        namespace = namespace if namespace else context["folder"]["name"]

        loaded_node = rv.commands.addSourceVerbose([filepath])

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

    def update(self, container, context):
        filepath = self.filepath_from_context(context)

        # change path
        node = container["node"]
        rv.commands.setSourceMedia(node, [filepath])

        # update colorspace
        representation = context["representation"]
        self.set_representation_colorspace(node, representation)

        # update name
        rv.commands.setStringProperty(f"{node}.media.name", ["newname"], True)
        rv.commands.setStringProperty(
            f"{node}.media.repName", ["repname"], True
        )
        rv.commands.setStringProperty(
            f"{node}.openpype.representation", [representation["id"]], True
        )

    def remove(self, container):
        node = container["node"]
        group = rv.commands.nodeGroup(node)
        rv.commands.deleteNode(group)

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
