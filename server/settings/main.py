from ayon_server.settings import (
    BaseSettingsModel,
    SettingsField,
)

from .actions import (
    ACTIONS_DEFAULT_VALUES,
    ActionsModel,
)

from .imageio import ImageIOSettings


class NetworkSettings(BaseSettingsModel):
    conn_name: str = SettingsField(
        title="Connection Name",
        default_factory=str,
    )
    conn_port: int = SettingsField(
        title="Connection Port",
        default_factory=int,
    )
    timeout: int = SettingsField(
        title="Timeout in Seconds",
        default_factory=int,
    )

class OpenRVSettings(BaseSettingsModel):
    enabled: bool = SettingsField(True)
    network: NetworkSettings = SettingsField(
        title="Network Settings",
        default_factory=NetworkSettings,
    )
    imageio: ImageIOSettings = SettingsField(
        default_factory=ImageIOSettings,
        title="Color Management (imageio)",
    )
    actions: ActionsModel = SettingsField(
        title="Actions",
        default_factory=ActionsModel,
    )

DEFAULT_VALUES = {
    "network": {
        "conn_name": "ayon-rv-connect",
        "conn_port": 45124,
        "timeout": 20,
    },
    "actions": ACTIONS_DEFAULT_VALUES,
}
