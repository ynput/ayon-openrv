""" Providing models and setting values for image IO in OpenRV.
    Copied from maya's settings
"""
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
    """Maya color management project settings.

    Todo: What to do with color management preferences version?
    """

    _isGroup: bool = True
    activate_host_color_management: bool = SettingsField(
        True, title="Enable Color Management"
    )
    ocio_config: ImageIOConfigModel = SettingsField(
        default_factory=ImageIOConfigModel,
        title="OCIO config"
    )


DEFAULT_IMAGEIO_SETTINGS = {
    "activate_host_color_management": True,
    "ocio_config": {
        "override_global_config": False,
        "filepath": []
    },
}
