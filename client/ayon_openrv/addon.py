import os

from ayon_core.addon import AYONAddon, IHostAddon
from ayon_core.addon.interfaces import IPluginPaths


OPENRV_ROOT_DIR = os.path.dirname(os.path.abspath(__file__))


class OpenRVAddon(AYONAddon, IHostAddon, IPluginPaths):
    name = "openrv"
    host_name = "openrv"

    def initialize(self, module_settings):
        self.enabled = True

    def get_plugin_paths(self):
        """Implementation of IPluginPaths to get plugin paths."""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        plugins_dir = os.path.join(current_dir, "plugins")

        return {
            "load": [os.path.join(plugins_dir, "actions")]
        }

    def add_implementation_envs(self, env, app):
        """Modify environments to contain all required for implementation."""
        # Set default environments if are not set via settings
        defaults = {
            "AYON_LOG_NO_COLORS": "True"
        }
        for key, value in defaults.items():
            if not env.get(key):
                env[key] = value

    def get_launch_hook_paths(self, app):
        if app.host_name != self.host_name:
            return []
        return [
            os.path.join(OPENRV_ROOT_DIR, "hooks")
        ]

    def get_workfile_extensions(self):
        return [".rv"]
