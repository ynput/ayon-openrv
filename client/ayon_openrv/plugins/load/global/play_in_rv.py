import json

import ayon_api
from ayon_applications import ApplicationManager

from ayon_core.pipeline import load
from ayon_core.lib.transcoding import (
    IMAGE_EXTENSIONS, VIDEO_EXTENSIONS
)

from ayon_openrv.networking import RVConnector


class PlayInRV(load.LoaderPlugin):
    """Opens representation with network connected OpenRV

    Could be run from Loader in DCC or outside.
    It expects to be run only on representations published to any task!
    """

    product_types = {"*"}
    representations = {"*"}
    extensions = {
        ext.lstrip(".")
        for ext in IMAGE_EXTENSIONS | VIDEO_EXTENSIONS
    }

    label = "Open in RV"
    order = -10
    icon = "play-circle"
    color = "orange"

    def load(self, context, name, namespace, data):
        rvcon = RVConnector()

        if not rvcon.is_connected:
            # get launch context variables
            project_name = context["project"]["name"]

            task_entity = None
            task_id = context["version"]["taskId"]
            # could be published without task from Publisher
            if task_id:
                task_entity = ayon_api.get_task_by_id(project_name, task_id)

            folder_entity = context["folder"]
            folder_path = folder_entity.get("path")
            # check required for host launch
            if not all([folder_path, task_entity]):
                raise Exception(f"Missing context data: {folder_path = }, "
                                f"{task_entity = }")

            # launch RV with context
            ctx = {
                "project_name": project_name,
                "folder_path": folder_path,
                "task_name": task_entity["name"]
            }

            app_manager = ApplicationManager()
            openrv_app = app_manager.find_latest_available_variant_for_group("openrv")
            if not openrv_app:
                raise RuntimeError(
                    f"No configured OpenRV found in "
                    f"Applications. Ask admin to configure it "
                    f"in ayon+settings://applications/applications/openrv.\n"
                    f"Provide '-network' there as argument."
                )
            openrv_app.launch(**ctx)

        repre_ext = context["representation"]["context"]["representation"]
        _data = [{
            "objectName": repre_ext,
            "representation": context["representation"]["id"],
        }]
        payload = json.dumps(_data)
        with rvcon: # this also retries the connection
            rvcon.send_event(
                "ayon_load_container", payload, shall_return=False)
