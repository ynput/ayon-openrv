import os

from ayon_core.addon import AYONAddon, IHostAddon, IPluginPaths


OPENRV_ROOT_DIR = os.path.dirname(os.path.abspath(__file__))


class OpenRVAddon(AYONAddon, IHostAddon, IPluginPaths):
    name = "openrv"
    host_name = "openrv"

    def initialize(self, module_settings):
        self.enabled = True

    def get_plugin_paths(self):
        return {}

    def get_create_plugin_paths(self, host_name):
        if host_name != self.host_name:
            return []
        plugins_dir = os.path.join(OPENRV_ROOT_DIR, "plugins")
        return [os.path.join(plugins_dir, "create")]

    def get_publish_plugin_paths(self, host_name):
        if host_name != self.host_name:
            return []
        plugins_dir = os.path.join(OPENRV_ROOT_DIR, "plugins")
        return [os.path.join(plugins_dir, "publish")]

    def get_load_plugin_paths(self, host_name):
        plugins_dir = os.path.join(OPENRV_ROOT_DIR, "plugins")
        if host_name != self.host_name:
            # for Tray Loader
            return [os.path.join(plugins_dir, "universal_load")]
        # inside OpenRV only - import rv
        return [os.path.join(plugins_dir, "load")]

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
