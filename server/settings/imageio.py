"""Providing models and setting values for image IO in OpenRV."""

from ayon_server.settings import (
    BaseSettingsModel,
    SettingsField,
)


class ImageIOConfigModel(BaseSettingsModel):
    override_global_config: bool = SettingsField(
        False,
        title="Override global OCIO config"
    )
    filepath: list[str] = SettingsField(
        default_factory=list,
        title="Config path"
    )


class ImageIOSettings(BaseSettingsModel):
    """OpenRV color management project settings."""

    _isGroup: bool = True
    activate_host_color_management: bool = SettingsField(
        True, title="Enable Color Management"
    )


DEFAULT_IMAGEIO_SETTINGS = {
    "activate_host_color_management": True,
}
