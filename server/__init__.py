from typing import Optional, Type, TYPE_CHECKING

from ayon_server.actions import (
    ActionContext,
    SimpleActionManifest,
)
from ayon_server.addons import BaseServerAddon
from ayon_server.addons.library import AddonLibrary
from ayon_server.forms import SimpleForm
from ayon_server.forms.simple_form import FormSelectOption
from ayon_server.lib.postgres import Postgres

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
        return [
            SimpleActionManifest(
                identifier="openrv.open_workfile",
                label="Open RV workfile",
                category="Desktop tools",
                order=100,
                icon={
                    "type": "material-symbols",
                    "name": "live_tv",
                    "color": "#FFA500",
                },
                entity_type="version",
                entity_subtypes=None,
                allow_multiselection=False,
            )
        ]

    # TODO: When dynamic actions work on the server then implement the action
    #  here to only show it on valid versions it can actually run on.
    # async def get_dynamic_actions(
    #     self,
    #     context: ActionContext,
    #     variant: str = "production",
    # ) -> list[DynamicActionManifest]:
    #     if not await self._can_open_rv_workfile(context):
    #         return []
    #
    #     return [
    #         DynamicActionManifest(
    #             identifier="openrv.open_workfile",
    #             label="Open RV workfile",
    #             category="Desktop tools",
    #             order=100,
    #             icon={
    #                 "type": "material-symbols",
    #                 "name": "live_tv",
    #                 "color": "#FFA500",
    #             },
    #         )
    #     ]

    async def _can_open_rv_workfile(self, context: ActionContext) -> bool:
        project_name = context.project_name
        entity_ids = context.entity_ids or []
        if not project_name:
            return False

        if context.entity_type != "version" or len(entity_ids) != 1:
            return False

        representation_id = await self._get_rv_workfile_representation_id(
            project_name,
            entity_ids[0],
        )
        return representation_id is not None

    async def _get_rv_workfile_representation_id(
        self,
        project_name: str,
        version_id: str,
    ) -> Optional[str]:
        # Must have `workfile` product base type and `rv` representation.
        query = f"""
            SELECT r.id
            FROM project_{project_name}.versions AS v
            JOIN project_{project_name}.products AS p
                ON p.id = v.product_id
            JOIN project_{project_name}.representations AS r
                ON r.version_id = v.id
            WHERE v.id = $1
                AND (
                    p.product_base_type = 'workfile'
                    OR p.product_type = 'workfile'
                )
                AND lower(r.name) = 'rv'
            LIMIT 1
        """
        result = await Postgres.fetchrow(query, version_id)

        if not result:
            return None
        return result["id"]

    async def _get_openrv_variant_options(
        self,
        settings_variant: str,
    ) -> list[tuple[str, str]]:
        library = AddonLibrary.getinstance()
        addons_by_name = await library.get_addons_by_variant(settings_variant)
        applications_addon = addons_by_name.get("applications")
        if applications_addon is None:
            raise Exception(
                f"Applications addon not found in bundle:"
                f" {settings_variant}..."
            )

        addon_studio_settings = await applications_addon.get_studio_settings(
            variant=settings_variant
        )

        if not addon_studio_settings:
            raise Exception(
                f"Could not load applications addon settings for"
                f" variant: {settings_variant}..."
            )
        applications_settings = getattr(
            addon_studio_settings, "applications", None
        )
        openrv_settings = getattr(applications_settings, "openrv", None)
        if openrv_settings is None:
            return []

        group_label = getattr(openrv_settings, "label", "") or "openrv"
        variants = getattr(openrv_settings, "variants", []) or []
        output: list[tuple[str, str]] = []
        for variant in variants:
            variant_name = getattr(variant, "name", None)
            if not variant_name:
                continue
            variant_label = getattr(variant, "label", "") or variant_name
            output.append(
                (
                    f"openrv/{variant_name}",
                    f"{group_label} {variant_label}",
                )
            )
        return output

    async def execute_action(
        self,
        executor: "ActionExecutor",
    ) -> "ExecuteResponseModel":
        context = executor.context

        if executor.identifier != "openrv.open_workfile":
            return await executor.get_server_action_response(
                success=False,
                message=(
                    f"Unsupported action identifier: {executor.identifier}"
                ),
            )

        if context.entity_type != "version":
            return await executor.get_server_action_response(
                success=False,
                message=(
                    f"Unsupported entity type in action context: {context}"
                ),
            )

        entity_ids = context.entity_ids or []
        if len(entity_ids) != 1:
            return await executor.get_server_action_response(
                success=False,
                message="Action requires exactly one selected version.",
            )

        project_name = context.project_name
        version_id = entity_ids[0]
        representation_id = await self._get_rv_workfile_representation_id(
            project_name,
            version_id,
        )
        if representation_id is None:
            return await executor.get_server_action_response(
                success=False,
                message="Selected workfile has no 'rv' representation.",
            )

        form_data = context.form_data or {}
        app_variant = form_data.get("app_variant")
        variant_options = await self._get_openrv_variant_options(
            executor.variant
        )
        if not app_variant and len(variant_options) == 1:
            app_variant = variant_options[0][0]

        if not app_variant:
            if not variant_options:
                return await executor.get_server_action_response(
                    success=False,
                    message=(
                        "No OpenRV variants are configured in Applications "
                        "settings for this bundle variant."
                    ),
                )

            form = SimpleForm()
            form.label("Select OpenRV version to launch")
            form.select(
                name="app_variant",
                label="OpenRV variant",
                options=[
                    FormSelectOption(
                        value=value,
                        label=label,
                    )
                    for value, label in variant_options
                ],
                value=variant_options[0][0],
            )
            return await executor.get_server_action_response(
                success=True,
                form=form,
                message="Select OpenRV variant",
            )

        allowed_variants = {value for value, _ in variant_options}
        if app_variant not in allowed_variants:
            return await executor.get_server_action_response(
                success=False,
                message="Selected OpenRV variant is not available.",
            )

        return await executor.get_launcher_action_response(
            args=[
                "addon",
                "openrv",
                "open-workfile",
                "--project_name",
                project_name,
                "--app_variant",
                app_variant,
                "--representation_id",
                representation_id,
            ]
        )
