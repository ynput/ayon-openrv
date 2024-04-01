from ayon_server.settings import (
    BaseSettingsModel,
    SettingsField,
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

DEFAULT_VALUES = {
    "network": {
        "conn_name": "ayon-rv-connect",
        "conn_port": 45124,
    }
}
