from ayon_server.settings import (
    BaseSettingsModel,
    SettingsField,
    MultiplatformPathListModel,
)


from ayon_server.settings import BaseSettingsModel

DEFAULT_VALUES = {}


class OpenRVSettings(BaseSettingsModel):
    enabled: bool = SettingsField(True)
