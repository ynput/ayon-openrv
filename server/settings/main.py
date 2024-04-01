from ayon_server.settings import (
    BaseSettingsModel,
    SettingsField,
)

from .imageio import ImageIOSettings


class OpenRVSettings(BaseSettingsModel):
    enabled: bool = SettingsField(True)
    port: int = SettingsField(
        title="Connection Port",
        default_factory=int,
    )
    imageio: ImageIOSettings = SettingsField(
        default_factory=ImageIOSettings,
        title="Color Management (imageio)",
    )

DEFAULT_VALUES = {
  "port": 45124
}
