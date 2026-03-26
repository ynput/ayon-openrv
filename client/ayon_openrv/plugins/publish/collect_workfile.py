import os
import pyblish.api


class CollectWorkfile(pyblish.api.InstancePlugin):
    """Inject the current working file into context"""

    order = pyblish.api.CollectorOrder - 0.49
    label = "OpenRV Session Workfile"
    hosts = ["openrv"]
    families = ["workfile"]

    def process(self, instance):
        """Inject the current working file"""

        current_file = instance.context.data["currentFile"]
        folder, file = os.path.split(current_file)
        filename, ext = os.path.splitext(file)

        if not current_file:
            self.log.error("No current filepath detected. "
                           "Make sure to save your OpenRV session")
            return

        instance.data["representations"] = [{
            "name": ext.lstrip("."),
            "ext": ext.lstrip("."),
            "files": file,
            "stagingDir": folder,
        }]
