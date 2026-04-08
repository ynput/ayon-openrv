from typing import Optional, Type, TYPE_CHECKING

from ayon_server.actions import SimpleActionManifest
from ayon_server.addons import BaseServerAddon

from .action import (
    execute_open_in_rv_action,
    get_open_in_rv_simple_action,
)
from .settings import OpenRVSettings, DEFAULT_VALUES

if TYPE_CHECKING:
    from ayon_server.actions import ActionExecutor, ExecuteResponseModel


class OpenRVAddon(BaseServerAddon):
    settings_model: Type[OpenRVSettings] = OpenRVSettings

    async def get_default_settings(self):
        settings_model_cls = self.get_settings_model()
        return settings_model_cls(**DEFAULT_VALUES)

    async def get_simple_actions(
        self,
        project_name: Optional[str] = None,
        variant: str = "production",
    ) -> list[SimpleActionManifest]:
        return [get_open_in_rv_simple_action()]

    async def execute_action(
        self,
        executor: "ActionExecutor",
    ) -> "ExecuteResponseModel":
        return await execute_open_in_rv_action(executor)
