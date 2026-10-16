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
from ayon_core.lib.transcoding import IMAGE_EXTENSIONS, VIDEO_EXTENSIONS
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
        if host_name != self.host_name:
            return []
        loaders_dir = os.path.join(OPENRV_ROOT_DIR, "plugins", "load")
        return [os.path.join(loaders_dir, "openrv")]

    def get_loader_action_plugin_paths(self, host_name=None):
        actions_dir = os.path.join(OPENRV_ROOT_DIR, "plugins", "load_actions")
        if host_name != self.host_name:
            # Other hosts and tray browser
            return [os.path.join(actions_dir, "global")]
        # inside OpenRV
        return [os.path.join(actions_dir, "openrv")]

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
            .option(
                "--use-existing-rv-instance",
                is_flag=True,
                help="Use an existing OpenRV instance to open the representation",
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
        use_existing_rv_instance: bool = False,
    ):
        project_name = project
        if use_existing_rv_instance:
            return self._cli_open_representation_in_existing_rv(
                project_name,
                representation,
                app_name=app,
            )

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
            # A workfile is opened by a new instance as well. It has to get a
            # port no other session uses for the same reason as media, so the
            # instance is network connected and reachable on its own port.
            self._launch_openrv(
                project_name,
                folder_path,
                task_name,
                app_name=app,
                workfile_path=repre_path,
                unset_session_filename=True,
                network_port=self._get_free_network_port(),
            )
        else:
            # A new OpenRV instance is launched and the representation is
            # pushed over its network connection. The
            # 'AYON_LOADER_REPRESENTATIONS' env file is consumed while RV is
            # still creating its mode, which loaded nothing and left an empty
            # session.
            self.open_representations_in_new_rv(
                project_name, [repre_entity], app_name=app
            )

    def open_representations_in_new_rv(
        self,
        project_name: str,
        representations: list[dict[str, str]],
        app_name: str | None = None,
    ) -> int:
        """Open representations in a new OpenRV instance.

        The instance is launched on a network port no other session uses,
        and every representation is sent to it.

        Args:
            project_name (str): Project the representations belong to.
            representations (list[dict[str, str]]): Representation entities.
            app_name (Optional[str]): OpenRV application variant to launch.

        Returns:
            int: Network port the instance was launched on.

        """
        from ayon_core.pipeline.load import LoadError

        from ayon_openrv.networking import send_representation_to_existing_rv

        if not representations:
            raise RuntimeError("No representation passed to open in OpenRV.")

        network_port = self._get_free_network_port()
        folder_path, task_name = self._get_launch_context_for_representation(
            project_name, representations[0]
        )
        self.log.info("Launching OpenRV on network port %s.", network_port)
        self._launch_openrv(
            project_name,
            folder_path,
            task_name,
            app_name=app_name,
            network_port=network_port,
        )

        for representation in representations:
            self.log.info(
                "Sending representation '%s' to the OpenRV instance on port"
                " %s.",
                representation["id"],
                network_port,
            )
            try:
                send_representation_to_existing_rv(
                    project_name,
                    representation,
                    wait_for_connection=True,
                    port=network_port,
                )
            except LoadError as error:
                raise LoadError(
                    "OpenRV was launched on network port"
                    f" {network_port} but nothing is listening on it. Check"
                    " the OpenRV variant arguments and pre-launch hooks for"
                    " '-network' / '-networkPort' settings, they must not"
                    " override the port AYON passes."
                ) from error

        return network_port

    def _get_free_network_port(self) -> int:
        """Network port a new OpenRV instance can use.

        The configured port is used when no other session uses it, otherwise
        a free port is picked: a new instance must not try to share the port
        of a running session, it would not be able to start its network
        connection and stay empty. A session is detected by connecting to the
        port, a bind test does not see a session listening on another address
        of the machine.

        Returns:
            int: Network port for a new OpenRV instance.

        """
        from ayon_openrv.networking import (
            find_available_network_port,
            is_network_port_available,
            is_network_port_listening,
        )

        network_port = self._get_network_port()
        if is_network_port_available(network_port) and (
            not is_network_port_listening(network_port)
        ):
            return network_port
        return find_available_network_port()

    def _cli_open_representation_in_existing_rv(
        self,
        project: str,
        representation: str,
        app_name: str | None = None,
    ):
        from ayon_openrv.networking import (
            is_network_port_listening,
            send_representation_to_existing_rv,
        )

        repre_entity = ayon_api.get_representation_by_id(
            project, representation
        )
        if repre_entity is None:
            raise RuntimeError(
                "Could not find representation by the provided id."
            )
        extension = repre_entity.get("context", {}).get("ext")
        if not extension:
            repre_path = get_representation_path(project, repre_entity)
            if not repre_path:
                raise RuntimeError(
                    "Could not resolve the representation's media extension."
                )
            extension = os.path.splitext(repre_path)[1]
        extension = "." + extension.lstrip(".").lower()
        if extension not in IMAGE_EXTENSIONS | VIDEO_EXTENSIONS:
            raise RuntimeError(
                f"Representation extension '{extension}' is not supported"
                " in existing OpenRV. Only image and video representations"
                " can be opened; RV workfiles require a new OpenRV instance."
            )

        network_port = self._get_network_port()
        if not is_network_port_listening(network_port):
            # Nothing is listening on the configured port. Launching a new
            # OpenRV instance is what the user wants, asking them to pick
            # another option would only be confusing.
            self.log.info(
                "No OpenRV session is running on network port %s, launching"
                " a new OpenRV instance.",
                network_port,
            )
            return self._cli_open_representation(
                project,
                app_name,
                representation,
                use_existing_rv_instance=False,
            )

        self.log.info(
            "Sending representation '%s' to the OpenRV session on port %s.",
            repre_entity["id"],
            network_port,
        )
        send_representation_to_existing_rv(project, repre_entity)

    def _get_network_port(self) -> int:
        """Return the configured OpenRV network port."""
        try:
            settings = ayon_api.get_addon_settings(self.name, self.version)
            return int(settings["network"]["conn_port"])
        except Exception:
            return 45124

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
        network_port: int | None = None,
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
        app_args = ["-network"]
        if network_port is not None:
            app_args.extend(["-networkPort", str(network_port)])

        launch_kwargs = dict(
            project_name=project_name,
            folder_path=folder_path,
            task_name=task_name,
            workfile_path=workfile_path,
            env=env,
            app_args=app_args,
        )
        # Used by prelaunch hook to load on launch
        if representation_id is not None:
            launch_kwargs["representation_ids"] = [representation_id]
            launch_kwargs["start_last_workfile"] = False

        app_manager.launch(app_name, **launch_kwargs)
