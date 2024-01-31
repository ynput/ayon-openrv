from typing import Type

from ayon_server.addons import BaseServerAddon

from .settings import OpenRVSettings, DEFAULT_VALUES
from .version import __version__


class OpenRVAddon(BaseServerAddon):
    name = "openrv"
    title = "OpenRV"
    version = __version__
    settings_model: Type[OpenRVSettings] = OpenRVSettings

    async def get_default_settings(self):
        settings_model_cls = self.get_settings_model()
        return settings_model_cls(**DEFAULT_VALUES)
