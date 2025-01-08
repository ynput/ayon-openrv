import os

from ayon_core.addon import AYONAddon, IHostAddon, IPluginPaths

from .version import __version__

OPENRV_ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
DEV_MODE = bool(os.getenv("AYON_USE_DEV"))
if DEV_MODE:
    print("DEV MODE IS ON")



class OpenRVAddon(AYONAddon, IHostAddon, IPluginPaths):
    name = "openrv"
    host_name = "openrv"
    version = __version__

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
        loaders_dir = os.path.join(OPENRV_ROOT_DIR, "plugins", "load")
        if host_name != self.host_name:
            # Other hosts and tray browser
            return [os.path.join(loaders_dir, "global")]
        # inside OpenRV
        return [os.path.join(loaders_dir, "openrv")]

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
        if DEV_MODE:
            # In development mode, use the current directory's hooks
            return [
                os.path.join(os.getcwd(), "client/ayon_openrv/hooks")
            ]
        return [
            os.path.join(OPENRV_ROOT_DIR, "hooks")
        ]

    def get_workfile_extensions(self):
        return [".rv"]
