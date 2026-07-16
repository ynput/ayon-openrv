from typing import Optional, Type, TYPE_CHECKING

from ayon_server.actions import DynamicActionManifest
from ayon_server.addons import BaseServerAddon

from .action import (
    execute_open_in_rv_action,
    get_open_in_rv_action,
    can_open_in_rv,
)
from .settings import OpenRVSettings, DEFAULT_VALUES

if TYPE_CHECKING:
    from ayon_server.actions import ActionExecutor, ExecuteResponseModel


class OpenRVAddon(BaseServerAddon):
    settings_model: Type[OpenRVSettings] = OpenRVSettings

    async def get_default_settings(self):
        settings_model_cls = self.get_settings_model()
        return settings_model_cls(**DEFAULT_VALUES)

    async def get_dynamic_actions(
        self,
        context,
        variant: str = "production",
    ) -> list["DynamicActionManifest"]:
        """Return dynamic actions for the given context.

        The Open in RV action should only be shown when it is valid for the
        selected version (i.e. when can_open_in_rv(context) is True).
        """
        actions = []
        if await can_open_in_rv(context):
            actions.append(get_open_in_rv_action())
        return actions

    async def execute_action(
        self,
        executor: "ActionExecutor",
    ) -> "ExecuteResponseModel":
        return await execute_open_in_rv_action(executor)
