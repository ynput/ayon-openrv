from ayon_server.settings import (
    BaseSettingsModel,
    SettingsField,
)

from .imageio import ImageIOSettings, DEFAULT_IMAGEIO_SETTINGS


class OpenRVSettings(BaseSettingsModel):
    enabled: bool = SettingsField(True)

    imageio: ImageIOSettings = SettingsField(
        default_factory=ImageIOSettings,
        title="Color Management (imageio)",
    )

DEFAULT_VALUES = {}
