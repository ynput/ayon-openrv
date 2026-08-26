import json

from ayon_core.lib.transcoding import (
    IMAGE_EXTENSIONS, VIDEO_EXTENSIONS
)
from ayon_core.pipeline import load
from ayon_core.pipeline.load import LoadError

from ayon_openrv.networking import RVConnector


class PlayInExistingRV(load.LoaderPlugin):
    """Opens representation with network connected OpenRV

    Could be run from Loader in DCC or outside.
    It expects to be run only on representations published to any task!
    """

    product_base_types = {"*"}
    product_types = product_base_types
    representations = {"*"}
    extensions = {
        ext.lstrip(".")
        for ext in IMAGE_EXTENSIONS | VIDEO_EXTENSIONS
    }

    label = "Open in Existing RV"
    order = -10
    icon = "play-circle"
    color = "orange"

    def load(self, context, name, namespace, data):
        rv_connector = RVConnector()
        if not rv_connector.is_connected:
            raise LoadError(
                "No existing OpenRV connection found."
                " Make sure OpenRV is running and network connected."
            )

        payload = json.dumps([{
            "objectName": context["representation"]["name"],
            "representation": context["representation"]["id"],
        }])
        # This also retries the connection
        with rv_connector:
            rv_connector.send_event(
                "ayon_load_container",
                payload,
                shall_return=False
            )
