import pyblish.api

from ayon_core.lib import version_up
from ayon_core.pipeline import registered_host
from ayon_core.pipeline.publish import get_errored_plugins_from_context


class IncrementWorkfile(pyblish.api.InstancePlugin):
    """Increment the current workfile.

    Saves the current scene with an increased version number.
    """

    label = "Increment Workfile"
    order = pyblish.api.IntegratorOrder + 9.0
    hosts = ["openrv"]
    families = ["workfile"]
    optional = True

    def process(self, instance):
        errored_plugins = get_errored_plugins_from_context(instance.context)
        if errored_plugins:
            raise RuntimeError(
                "Skipping incrementing current file because publishing failed."
            )

        scene_path = version_up(instance.context.data["currentFile"])
        host = registered_host()
        host.save_workfile(scene_path)

        self.log.info("Incremented workfile to: {}".format(scene_path))
