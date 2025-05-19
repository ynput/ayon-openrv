import json
import tempfile

from ayon_applications import PreLaunchHook


class PreFtrackData(PreLaunchHook):
    """Pre-hook for openrv/ftrack."""
    app_groups = ["openrv"]

    def execute(self):

        representations = self.data.get("extra", None)
        if representations:
            payload = {"representations": representations}
            with tempfile.NamedTemporaryFile(mode="w+", delete=False) as file:
                json.dump(payload, file)

            self.launch_context.env["AYON_LOADER_REPRESENTATIONS"] = str(file.name)  # noqa
