"""Providing models and setting values for Actions in OpenRV."""

from ayon_server.settings import (
    BaseSettingsModel,
    SettingsField,
)

class HandlerOpenReviewSessionModel(BaseSettingsModel):
    """Settings for the OpenRV handler."""
    enabled: bool = SettingsField(
        title="Enabled",
        default=True,
    )
    default_representation: list[str] = SettingsField(
        title="Default Representation",
        default_factory=list,
        description=(
            "Default order of representation to be used for review session. "
            "Order is important and regex expressions are supported. "
        ),
    )

class ActionsModel(BaseSettingsModel):
    """Settings for the OpenRV actions."""
    app_variant_regex: str = SettingsField(
        title="App Variant Regex",
        default_factory=str,
        description=(
            "Regex expression to match the app variant. "
            "For example: ^openrv-.*$"
        ),
    )
    handler_open_review_session: HandlerOpenReviewSessionModel = SettingsField(
        title="Open Review Session",
        default_factory=HandlerOpenReviewSessionModel,
    )


ACTIONS_DEFAULT_VALUES = {
    "app_variant_regex": r"^openrv-.*$",
    "handler_open_review_session": {
        "enabled": True,
        "default_representation": [
            "^exr$",
        ],
    }
}
