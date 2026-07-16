import json
import tempfile

from ayon_applications import PreLaunchHook


class PassRepresentationsHook(PreLaunchHook):
    """Pre-hook for openrv."""
    app_groups = ["openrv"]

    def execute(self):
        representation_ids = self.data.get("representation_ids")
        if not representation_ids:
            return

        payload = {"representation_ids": representation_ids}
        with tempfile.NamedTemporaryFile(mode="w+", delete=False) as file:
            json.dump(payload, file)
            metadata_path = file.name

        self.launch_context.env["AYON_LOADER_REPRESENTATIONS"] = metadata_path
