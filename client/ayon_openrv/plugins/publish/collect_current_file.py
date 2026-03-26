import os
import pyblish.api

from ayon_core.pipeline import registered_host


class CollectCurrentFile(pyblish.api.ContextPlugin):
    """Inject the current working file into context"""

    order = pyblish.api.CollectorOrder - 0.5
    label = "Collect Current File"
    hosts = ["openrv"]

    def process(self, context):
        host = registered_host()
        current_file = host.get_current_workfile() or ""
        context.data["currentFile"] = current_file
