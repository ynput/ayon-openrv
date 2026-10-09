from ayon_core.lib.transcoding import (
    IMAGE_EXTENSIONS, VIDEO_EXTENSIONS
)
from ayon_core.pipeline import load

from ayon_openrv.networking import send_representation_to_existing_rv


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
        send_representation_to_existing_rv(
            context["project"]["name"],
            context["representation"]
        )
