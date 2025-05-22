import logging
from typing import Type

from ayon_server.addons import BaseServerAddon
from ayon_server.forms import SimpleForm
from ayon_server.actions import (
    ActionExecutor,
    ExecuteResponseModel,
    SimpleActionManifest,
)
from .action_handlers import (
    open_review_session_action,
)
from .settings import DEFAULT_VALUES, OpenRVSettings


class OpenRVAddon(BaseServerAddon):
    settings_model: Type[OpenRVSettings] = OpenRVSettings

    async def get_default_settings(self):
        settings_model_cls = self.get_settings_model()
        return settings_model_cls(**DEFAULT_VALUES)

    async def get_simple_actions(
        self,
        project_name: str | None = None,
        variant: str = "production",
    ) -> list[SimpleActionManifest]:
        """Return a list of simple actions provided by the addon"""

        _ = project_name  # Unused
        _ = variant  # Unused
        return [
            open_review_session_action.ENTRYPOINT
        ]

    async def execute_action(
        self,
        executor: ActionExecutor,
    ) -> ExecuteResponseModel:
        """Execute an action provided by the addon"""

        try:
            if executor.identifier == "openrv-run-review-session":
                # We only expose delivery-run-delivery action
                return await open_review_session_action.handler_open_review_session(
                    self, executor)
        except Exception as e:
            form = SimpleForm()
            form.label(f"Error: {e}", highlight="error")
            form.hidden("step", "failed")
            logging.error(f"Error executing action: {e}", exc_info=True)
            # Alternative logging approach:
            # error_traceback = traceback.format_exc()
            # logging.error(f"Error executing action: {e}\n{error_traceback}")
            return await executor.get_server_action_response(
                form=form,
                success=True,
            )

        raise ValueError(f"Invalid action identifier: {executor.identifier}")
