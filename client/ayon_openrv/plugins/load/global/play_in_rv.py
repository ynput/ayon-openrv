import json

import ayon_api
from ayon_applications import ApplicationManager

from ayon_core.lib.transcoding import (
    IMAGE_EXTENSIONS, VIDEO_EXTENSIONS
)
from ayon_core.pipeline import load
from ayon_core.pipeline.load import LoadError

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
            project_name, folder_path, task_name = (
                self._get_lauch_context(context)
            )
            # launch RV with context
            app_manager = ApplicationManager()
            openrv_app = app_manager.find_latest_available_variant_for_group(
                "openrv"
            )
            if not openrv_app:
                raise LoadError(
                    "No configured OpenRV found in"
                    " Applications. Ask admin to configure it"
                    " in ayon+settings://applications/applications/openrv."
                    "\nProvide '-network' there as argument."
                )
            openrv_app.launch(
                project_name=project_name,
                folder_path=folder_path,
                task_name=task_name
            )

        payload = json.dumps([{
            "objectName": context["representation"]["name"],
            "representation": context["representation"]["id"],
        }])
        # This also retries the connection
        with rvcon:
            rvcon.send_event(
                "ayon_load_container",
                payload,
                shall_return=False
            )

    def _get_lauch_context(self, context):
        # get launch context variables
        project_name = context["project"]["name"]

        folder_entity = context["folder"]
        folder_path = folder_entity.get("path")
        if not folder_path:
            raise LoadError(
                "Selected representation does not have available folder."
                " It is not possible to start OpenRV."
            )

        task_entity = None
        task_id = context["version"]["taskId"]
        # could be published without task from Publisher
        if task_id:
            task_entity = ayon_api.get_task_by_id(project_name, task_id)

        if not task_entity:
            repre_context = context["representation"]["context"]
            task_info = repre_context.get("task")
            task_name = None
            if task_info:
                if isinstance(task_info, str):
                    task_name = task_info
                elif isinstance(task_info, dict):
                    task_name = task_info.get("name")

            if task_name:
                task_entity = ayon_api.get_task_by_name(
                    project_name, folder_entity["id"], task_name
                )

        if task_entity:
            return project_name, folder_path, task_entity["name"]

        raise LoadError(
            "Selected representation does not have available task."
            " It is not possible to start OpenRV."
        )
