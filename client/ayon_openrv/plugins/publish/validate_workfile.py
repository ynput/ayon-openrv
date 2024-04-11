import pyblish.api

from ayon_core.pipeline.publish import PublishValidationError


class ValidateCurrentWorkFile(pyblish.api.InstancePlugin):
    """There must be workfile to publish."""

    label = "Validate Workfile"
    order = pyblish.api.ValidatorOrder - 0.1
    hosts = ["openrv"]
    families = ["workfile"]

    def process(self, instance):
        current_file = instance.context.data["currentFile"]
        if not current_file:
            raise PublishValidationError("There is no workfile to publish.")
