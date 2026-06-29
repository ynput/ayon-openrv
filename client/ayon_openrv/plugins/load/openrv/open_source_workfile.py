from __future__ import annotations

import os

import rv
from ayon_api import (
    get_folder_by_id,
    get_product_by_id,
    get_representation_by_id,
    get_task_by_id,
    get_version_by_id,
)
from ayon_core.addon import AddonsManager
from ayon_core.pipeline import Anatomy, get_current_project_name
from qtpy.QtWidgets import QMessageBox


class OpenSourceWorkfileError(RuntimeError):
    """Raised when source workfile launch data cannot be resolved."""


def get_current_representation_id() -> tuple[str | None, str | None]:
    """Get representation id and project from current RV view node."""
    try:
        sources = rv.commands.sourcesAtFrame(rv.commands.frame())
        if not sources:
            return None, None
        node_name = sources[0]
    except Exception:
        print("Failed to collect sources at current frame.")
        return None, None

    try:
        source_nodes = rv.commands.nodesOfType("RVFileSource")
    except Exception:
        print("Failed to list RVFileSource nodes.")
        return None, None

    for node in source_nodes:
        if not node_name.startswith(str(node)):
            continue

        try:
            repre_ids = rv.commands.getStringProperty(
                f"{node}.ayon.representation"
            )
        except Exception:
            continue

        try:
            project_names = rv.commands.getStringProperty(
                f"{node}.ayon.project_name"
            )
        except Exception:
            project_names = []

        repre_id = next(iter(repre_ids), None)
        if not repre_id:
            continue

        project_name = next(iter(project_names), None)
        return repre_id, project_name or get_current_project_name()

    return None, None


def open_source_workfile(parent_widget=None) -> None:
    """Resolve and launch source workfile for currently viewed RV source."""
    repre_id, project_name = get_current_representation_id()
    if not repre_id or not project_name:
        QMessageBox.warning(
            parent_widget,
            "Open Source Workfile",
            "No representation found on the current view node.",
        )
        return

    try:
        app_name, workfile_path = launch_source_workfile_from_representation(
            project_name,
            repre_id,
        )
    except OpenSourceWorkfileError as exc:
        QMessageBox.warning(
            parent_widget,
            "Open Source Workfile",
            str(exc),
        )
        return
    except Exception as exc:
        print("Unexpected error in open_source_workfile flow.")
        QMessageBox.critical(
            parent_widget,
            "Open Source Workfile",
            f"Failed to open source workfile:\n{exc}",
        )
        return

    workfile_name = os.path.basename(workfile_path)
    rv.extra_commands.displayFeedback(
        f"Launching {app_name} with: {workfile_name}",
        4.0,
    )


def _resolve_launch_context(project_name: str, version: dict) -> tuple[str, str]:
    product_id = version.get("productId")
    if not product_id:
        raise OpenSourceWorkfileError(
            "Could not find product id on the parent version."
        )

    product = get_product_by_id(project_name, product_id)
    if not product:
        raise OpenSourceWorkfileError(
            "Could not find product entity for this version."
        )

    folder_id = product.get("folderId")
    if not folder_id:
        raise OpenSourceWorkfileError(
            "Could not find folder id on the product entity."
        )

    folder = get_folder_by_id(project_name, folder_id)
    if not folder:
        raise OpenSourceWorkfileError(
            "Could not find folder entity for this version."
        )

    folder_path = folder.get("path")
    task_id = version.get("taskId")
    task = get_task_by_id(project_name, task_id) if task_id else None
    task_name = task.get("name") if task else None

    if not folder_path or not task_name:
        raise OpenSourceWorkfileError(
            "Cannot launch application without folder and task context.\n\n"
            f"Folder path: {folder_path}\n"
            f"Task name: {task_name}"
        )
    return folder_path, task_name


def launch_source_workfile_from_representation(
        project_name: str,
        representation_id: str,
) -> tuple[str, str]:
    """Resolve source workfile from representation and launch its DCC app.

    Returns:
        tuple[str, str]: Tuple of launched app name and resolved workfile path.
    """

    representation = get_representation_by_id(project_name, representation_id)
    if not representation:
        raise OpenSourceWorkfileError("Could not find representation entity.")

    version_id = representation.get("versionId")
    if not version_id:
        raise OpenSourceWorkfileError(
            "Could not find version id on representation entity."
        )

    version = get_version_by_id(
        project_name,
        version_id,
        fields={"id", "attrib", "data", "productId", "taskId"},
    )
    if not version:
        raise OpenSourceWorkfileError("Could not find version entity.")

    source_path = version.get("attrib", {}).get("source")
    if not source_path:
        raise OpenSourceWorkfileError(
            "This version does not have source workfile information."
        )

    workfile_path = Anatomy(project_name).fill_root(source_path)
    if not workfile_path or not os.path.exists(workfile_path):
        raise OpenSourceWorkfileError(
            "Resolved source workfile path does not exist:\n\n"
            f"{workfile_path}"
        )

    addons_manager = AddonsManager()
    applications_addon = addons_manager.get("applications")
    if not applications_addon:
        raise OpenSourceWorkfileError("Applications addon not found.")

    app_manager = applications_addon.get_applications_manager()
    app_name = version.get("data", {}).get("ayon_app_name")
    if not app_name:
        raise OpenSourceWorkfileError(
            "No application name found for:\n\n"
            f"{workfile_path}"
        )

    folder_path, task_name = _resolve_launch_context(project_name, version)

    # Build a clean env for the DCC launch.
    # Filter out ALL OpenRV-specific PYTHONPATH entries using two prefixes:
    #   1. rv_root  = dirname(dirname(sys.executable)) e.g. C:\OpenRV_3.1.0
    #   2. RV_SUPPORT_PATH = the temp dir with deployed RV packages
    # PYTHONHOME (set by OpenRV to its own root) is also removed; it would
    # redirect the DCC's Python to look in the wrong location.
    import sys
    _rv_root = os.path.normpath(
        os.path.dirname(os.path.dirname(sys.executable))
    )
    _rv_support = os.path.normpath(
        os.environ.get("RV_SUPPORT_PATH", "\x00no_match\x00")
    )
    _orig_pp = os.environ.get("PYTHONPATH", "")

    def _keep_path(p):
        n = os.path.normpath(p)
        return not n.startswith(_rv_root) and not n.startswith(_rv_support)

    launch_env = os.environ.copy()
    launch_env["PYTHONPATH"] = os.pathsep.join(
        p for p in _orig_pp.split(os.pathsep) if p and _keep_path(p)
    )
    for _key in (
        "PYTHONHOME",
        "RV_SUPPORT_PATH", "AYON_HOST_NAME",
        "AYON_WORKDIR", "AYON_PROJECT_NAME",
        "AYON_FOLDER_PATH", "AYON_TASK_NAME", "AYON_TASK_TYPE",
    ):
        launch_env.pop(_key, None)

    app_manager.launch(
        app_name,
        project_name=project_name,
        folder_path=folder_path,
        task_name=task_name,
        workfile_path=workfile_path,
        env=launch_env,
    )

    return app_name, workfile_path
