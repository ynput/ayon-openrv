import json

from ayon_applications import ApplicationManager

from ayon_core.pipeline import load

from ayon_openrv.networking import RVConnector


class PlayInRV(load.LoaderPlugin):
    """Open Image Sequence with system default"""

    product_types = {"*"}
    representations = {"*"}
    extensions = {
        "cin", "dpx", "avi", "dv", "gif", "flv", "mkv", "mov", "mpg", "mpeg",
        "mp4", "m4v", "mxf", "iff", "z", "ifl", "jpeg", "jpg", "jfif", "lut",
        "1dl", "exr", "pic", "png", "ppm", "pnm", "pgm", "pbm", "rla", "rpf",
        "sgi", "rgba", "rgb", "bw", "tga", "tiff", "tif", "img", "h264",
    }

    label = "Open in RV"
    order = -10
    icon = "play-circle"
    color = "orange"

    def load(self, context, name, namespace, data):
        rvcon = RVConnector()

        if not rvcon.is_connected:
            app_manager = ApplicationManager()

            # get launch context variables
            task = context["representation"]["data"]["context"].get("task")
            folder_path = context["folder"].get("path")
            if not all([folder_path, task]):
                raise Exception(f"Missing context data: {folder_path = }, {task = }")

            # launch RV with context
            ctx = {
                "project_name": context["project"]["name"],
                "folder_path": folder_path,
                "task_name": task["name"] or "generic",
            }
            openrv_app = app_manager.find_latest_available_variant_for_group("openrv")
            openrv_app.launch(**ctx)

        _data = [{
            "objectName": context["representation"]["context"]["representation"],
            "representation": context["representation"]["id"],
        }]
        payload = json.dumps(_data)
        with rvcon: # this also retries the connection
            rvcon.send_event("ayon_load_container", payload, shall_return=False)
