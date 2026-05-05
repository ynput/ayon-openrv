from __future__ import annotations

import os

import ayon_api

from ayon_core.addon import (
    AYONAddon,
    IHostAddon,
    IPluginPaths,
    click_wrap,
    ensure_addons_are_process_ready,
)
from ayon_core.pipeline import get_representation_path


from .constants import OPENRV_ROOT_DIR
from .version import __version__


class OpenRVAddon(AYONAddon, IHostAddon, IPluginPaths):
    name = "openrv"
    host_name = "openrv"
    version = __version__

    def get_plugin_paths(self):
        return {}

    def get_create_plugin_paths(self, host_name):
        if host_name != self.host_name:
            return []
        plugins_dir = os.path.join(OPENRV_ROOT_DIR, "plugins")
        return [os.path.join(plugins_dir, "create")]

    def get_publish_plugin_paths(self, host_name):
        if host_name != self.host_name:
            return []
        plugins_dir = os.path.join(OPENRV_ROOT_DIR, "plugins")
        return [os.path.join(plugins_dir, "publish")]

    def get_load_plugin_paths(self, host_name):
        loaders_dir = os.path.join(OPENRV_ROOT_DIR, "plugins", "load")
        if host_name != self.host_name:
            # Other hosts and tray browser
            return [os.path.join(loaders_dir, "global")]
        # inside OpenRV
        return [os.path.join(loaders_dir, "openrv")]

    def add_implementation_envs(self, env, app):
        """Modify environments to contain all required for implementation."""
        # Set default environments if are not set via settings
        defaults = {
            "AYON_LOG_NO_COLORS": "True"
        }
        for key, value in defaults.items():
            if not env.get(key):
                env[key] = value

    def get_launch_hook_paths(self, app):
        if app.host_name != self.host_name:
            return []
        return [
            os.path.join(OPENRV_ROOT_DIR, "hooks")
        ]

    def get_workfile_extensions(self):
        return [".rv"]

    def cli(self, addon_click_group):
        main_group = click_wrap.group(
            self._cli_main, name=self.name, help="OpenRV addon"
        )
        (
            main_group.command(
                self._cli_open_workfile,
                name="open-workfile",
                help="Open a published RV workfile in OpenRV",
            )
            .option("--project", required=True, help="Project name")
            .option(
                "--representation",
                required=True,
                help="Published RV workfile representation id",
            )
            .option(
                "--app",
                required=False,
                default=None,
                help="OpenRV app variant full name (e.g. openrv/2025)",
            )
        )
        (
            main_group.command(
                self._cli_open_representation,
                name="open-representation",
                help=(
                    "Open a published RV workfile or media representation"
                    " in OpenRV"
                ),
            )
            .option("--project", required=True, help="Project name")
            .option(
                "--representation",
                required=True,
                help="Published representation id",
            )
            .option(
                "--app",
                required=False,
                default=None,
                help="OpenRV app variant full name (e.g. openrv/2025)",
            )
        )
        addon_click_group.add_command(main_group.to_click_obj())

    def _cli_main(self):
        ensure_addons_are_process_ready(
            addon_name=self.name,
            addon_version=self.version,
        )

    def _cli_open_workfile(
        self,
        project: str,
        app: str,
        representation: str
    ):
        project_name = project
        repre_entity = ayon_api.get_representation_by_id(
            project_name,
            representation,
        )
        if repre_entity is None:
            raise RuntimeError(
                "Could not find representation by the provided id."
            )

        repre_path = get_representation_path(project_name, repre_entity)
        folder_path, task_name = (
            self._get_launch_context_for_representation(
                project_name, repre_entity
            )
        )
        self._launch_openrv(
            project_name,
            folder_path,
            task_name,
            app_name=app,
            workfile_path=repre_path,
            # After opening unset the session filename to avoid user
            # accidentally saving into the published file.
            unset_session_filename=True,
        )

    def _cli_open_representation(
        self,
        project: str,
        app: str,
        representation: str,
    ):
        project_name = project
        repre_entity = ayon_api.get_representation_by_id(
            project_name,
            representation,
        )
        if repre_entity is None:
            raise RuntimeError(
                "Could not find representation by the provided id."
            )

        folder_path, task_name = (
            self._get_launch_context_for_representation(
                project_name, repre_entity
            )
        )

        if repre_entity["name"] == "rv":
            repre_path = get_representation_path(project_name, repre_entity)
            self._launch_openrv(
                project_name,
                folder_path,
                task_name,
                app_name=app,
                workfile_path=repre_path,
                unset_session_filename=True,
            )
        else:
            self._launch_openrv(
                project_name,
                folder_path,
                task_name,
                app_name=app,
                representation_id=representation,
            )

    def _get_launch_context_for_representation(
        self,
        project_name: str,
        representation: dict[str, str],
    ) -> tuple[str, str]:
        version = ayon_api.get_version_by_id(
            project_name,
            representation["versionId"],
            fields={"productId", "taskId"},
        )
        if not version:
            raise RuntimeError(
                f"Could not resolve parent version for representation "
                f"'{representation['id']}'."
            )

        product = ayon_api.get_product_by_id(
            project_name,
            version["productId"],
            fields={"folderId"},
        )
        if not product:
            raise RuntimeError(
                f"Could not resolve parent product for representation "
                f"'{representation['id']}'."
            )

        folder = ayon_api.get_folder_by_id(
            project_name,
            product["folderId"],
            fields={"path"},
        )
        folder_path = folder.get("path") if folder else None
        if not folder_path:
            raise RuntimeError(
                f"Could not resolve folder path for representation "
                f"'{representation['id']}'."
            )

        task_name = None
        task_id = version.get("taskId")
        if task_id:
            task = ayon_api.get_task_by_id(
                project_name,
                task_id,
                fields={"name"},
            )
            if task:
                task_name = task.get("name")

        return folder_path, task_name

    def _launch_openrv(
        self,
        project_name: str,
        folder_path: str,
        task_name: str,
        *,
        app_name: str | None = None,
        workfile_path: str | None = None,
        unset_session_filename: bool = False,
        representation_id: str | None = None,
    ):
        from ayon_applications import ApplicationManager

        app_manager = ApplicationManager()
        if not app_name:
            openrv_app = app_manager.find_latest_available_variant_for_group(
                "openrv"
            )
            if not openrv_app:
                raise RuntimeError(
                    "No configured OpenRV found in Applications. Ask admin "
                    "to configure it in "
                    "ayon+settings://applications/applications/openrv."
                )
            app_name = openrv_app.full_name

        # Directly after opening the workfile, unset the session so the user
        # won't accidentally overwrite the passed workfile.
        env = os.environ.copy()
        if unset_session_filename:
            env["AYON_RV_UNSET_SESSION"] = "1"

        launch_kwargs = dict(
            project_name=project_name,
            folder_path=folder_path,
            task_name=task_name,
            workfile_path=workfile_path,
            env=env,
        )
        # Used by prelaunch hook to load on launch
        if representation_id is not None:
            launch_kwargs["representation_ids"] = [representation_id]
            launch_kwargs["start_last_workfile"] = False

        app_manager.launch(app_name, **launch_kwargs)
