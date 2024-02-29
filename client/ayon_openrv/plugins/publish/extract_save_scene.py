import pyblish.api
from ayon_core.pipeline import registered_host
from ayon_core.pipeline import publish, KnownPublishError


class ExtractSaveScene(pyblish.api.ContextPlugin):
    """Save scene before extraction."""

    order = publish.Extractor.order - 0.48
    label = "Extract Save Scene"
    hosts = ["openrv"]

    def process(self, context):
        host = registered_host()

        current_file_name = host.get_current_workfile()
        self.log.info("current_file_name::{}".format(current_file_name))
        if not current_file_name:
            raise KnownPublishError("Scene not saved, use Workfile app "
                                    "to save first!")
        host.save_workfile(current_file_name)
