import importlib
import json
import logging
import os
import sys
import traceback
from functools import partial

import rv.qtutils
from ayon_api import get_representations
from ayon_core.pipeline import (
    discover_loader_plugins,
    get_current_project_name,
    install_host,
    load_container,
    registered_host,
)
from ayon_core.settings import get_project_settings
from ayon_core.tools.utils import host_tools
from ayon_openrv.api import OpenRVHost
from ayon_openrv.networking import LoadContainerHandler
from qtpy.QtCore import QEvent, QObject, QTimer
from qtpy.QtWidgets import QApplication
from rv.rvtypes import MinorMode

# TODO (Critical) Remove this temporary hack to avoid clash with PyOpenColorIO
#   that is contained within AYON's venv
# Ensure PyOpenColorIO is loaded from RV instead of from AYON lib by
# moving all rv related paths to start of sys.path so RV libs are imported
# We consider the `/openrv` folder the root to  `/openrv/bin/rv` executable
rv_root = os.path.normpath(os.path.dirname(os.path.dirname(sys.executable)))
rv_paths = []
non_rv_paths = []
for path in sys.path:
    if os.path.normpath(path).startswith(rv_root):
        rv_paths.append(path)
    else:
        non_rv_paths.append(path)
sys.path[:] = rv_paths + non_rv_paths

import PyOpenColorIO  # noqa

importlib.reload(PyOpenColorIO)


def enable_python_debugger():
    if not os.environ.get("AYON_RV_DEBUG"):
        return

    import platform

    try:
        import debugpy
    except ImportError:
        logging.error("AYON_RV_DEBUG: Debugpy is not installed: ")
        return

    rv_interpreter = None
    system = platform.system().lower()
    if system == "darwin":
        rv_interpreter = f"{rv_root}/MacOS/python"
    else:
        logging.error(
            "AYON_RV_DEBUG: Debugger is not supported on this %s: "
            "implement me !",
            system,
        )

    if not rv_interpreter:
        logging.error("AYON_RV_DEBUG: Could not find RV interpreter")
        return

    logging.info(f"AYON_RV_DEBUG: Enable debugger: {rv_root}")
    debugpy.configure(python=f"{rv_root}/MacOS/python")
    debugpy.listen(("0.0.0.0", 5678))
    logging.info(
        "AYON_RV_DEBUG: Waiting for debugger to attach on port 5678..."
    )


def install_host_in_ayon():
    host = OpenRVHost()
    install_host(host)


class DockCloseFilter(QObject):
    def __init__(self, panel_name, callback, parent=None):
        super().__init__(parent)
        self._panel_name = panel_name
        self._callback = callback

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Close:
            self._callback(self._panel_name, False)
        elif event.type() == QEvent.Show:
            self._callback(self._panel_name, True)
        return False


class AYONMenus(MinorMode):
    def __init__(self):
        MinorMode.__init__(self)
        self.init(
            name="py-ayon",
            globalBindings=None,
            overrideBindings=[
                # event name, callback, description
                (
                    "ayon_load_container",
                    on_ayon_load_container,
                    "Loads an AYON representation into the session.",
                ),
                (
                    "session-initialized",
                    self._open_visible_panels,
                    "Open visible panels on session initialization",
                ),
            ],
            menu=[
                # Menu name
                # NOTE: If it already exists it will merge with existing
                # and add submenus / menuitems to the existing one
                ("AYON", self.menu_item()),
            ],
            # initialization order
            sortKey="source_setup",
            ordering=15,
        )
        self._panel_startup_visibility = []
        self._connected_panels = set()
        self._is_closing = False

    def _read_panel_startup_visibility(self):
        return rv.commands.readSettings("ayon", "panel_startup_visibility", [])

    def _write_panel_startup_visibility(self, panel_name: str, visible: bool):
        if self._is_closing:
            return

        if visible:
            if panel_name not in self._panel_startup_visibility:
                self._panel_startup_visibility.append(panel_name)
        else:
            if panel_name in self._panel_startup_visibility:
                self._panel_startup_visibility.remove(panel_name)
        rv.commands.writeSettings(
            "ayon", "panel_startup_visibility", self._panel_startup_visibility
        )

    def _open_visible_panels(self, event):
        event.reject()
        self._panel_startup_visibility: list[str] = (
            self._read_panel_startup_visibility()
        )

        for panel_name in self._panel_startup_visibility:
            QTimer.singleShot(
                0, lambda: self.open_desktop_review_panel(panel_name)
            )

    @property
    def _parent(self):
        return rv.qtutils.sessionWindow()

    def load(self, event):
        host_tools.show_loader(parent=self._parent, use_context=True)

    def publish(self, event):
        host_tools.show_publisher(parent=self._parent, tab="publish")

    def workfiles(self, event):
        host_tools.show_workfiles(parent=self._parent)

    def scene_inventory(self, event):
        host_tools.show_scene_inventory(parent=self._parent)

    def library(self, event):
        host_tools.show_library_loader(parent=self._parent)

    def _on_app_closing(self):
        self._is_closing = True

    def open_desktop_review_panel(self, panel_name: str, *_):
        panel = self.review_controller.get_panel(panel_name)
        dock_widget = self.review_controller.set_docker_widget(
            self._parent, panel, panel_name
        )
        # get the data
        self.review_controller.set_project(get_current_project_name() or "")
        self.review_controller.load_ayon_data()

        if dock_widget and panel_name not in self._connected_panels:
            filter_ = DockCloseFilter(
                panel_name,
                self._write_panel_startup_visibility,
                parent=dock_widget,
            )
            dock_widget.installEventFilter(filter_)
            self._connected_panels.add(panel_name)

        # # allow panel to show now.
        # QApplication.instance().processEvents()

    def add_desktop_review_menu_items(self, menu):
        # Check if addon is enabled
        project_settings = get_project_settings(get_current_project_name())
        review_desktop = project_settings.get("review_desktop", {})
        if not review_desktop.get("enabled", False):
            return
        # import review desktop controler
        try:
            from ayon_review_desktop import ReviewController
        except ImportError:
            print("Failed to import 'ayon_review_desktop':")
            traceback.print_exc()
            return
        # instance controler and return the menu items.
        self.review_controller = ReviewController(host="rv")
        menu.append(("_", None))  # separator
        for k, panel_name in enumerate(
            self.review_controller.get_available_panels()
        ):
            label = panel_name.replace("_", " ").capitalize()
            menu.append(
                (
                    f"{label}...",
                    partial(self.open_desktop_review_panel, panel_name),
                    f"control shift {k + 1}",
                    None,
                )
            )

    def menu_item(self):
        menu = [
            # Menuitem name, actionHook (event), key, stateHook
            ("Load...", self.load, None, None),
            ("Publish...", self.publish, None, None),
            ("Manage...", self.scene_inventory, None, None),
            ("Library...", self.library, None, None),
            ("_", None),  # separator
            ("Work Files...", self.workfiles, None, None),
        ]
        # Add Activity Stream menu item if enabled in project settings
        self.add_desktop_review_menu_items(menu)

        # Add a callback to detect when RV is closing
        QApplication.instance().aboutToQuit.connect(self._on_app_closing)

        return menu


def data_loader():
    incoming_data_file = os.environ.get("AYON_LOADER_REPRESENTATIONS", None)
    if incoming_data_file:
        with open(incoming_data_file, "rb") as file:
            decoded_data = json.load(file)
        os.remove(incoming_data_file)
        load_data(dataset=decoded_data["representations"])
    else:
        print("No data for auto-loader")


def on_ayon_load_container(event):
    handler = LoadContainerHandler(event)
    handler.handle_event()


def load_data(dataset=None):
    project_name = get_current_project_name()
    available_loaders = discover_loader_plugins(project_name)
    Loader = next(
        loader
        for loader in available_loaders
        if loader.__name__ == "FramesLoader"
    )

    representations = get_representations(
        project_name, representation_ids=dataset
    )

    for representation in representations:
        load_container(Loader, representation)


# only add menu items if AYON_RV_NO_MENU is not set to 1
if os.getenv("AYON_RV_NO_MENU") != "1":

    def createMode():
        # This function triggers for each RV session window being opened, for
        # example when using File > New Session this will trigger again. As such
        # we only want to trigger the startup install when the host is not
        # registered yet.
        if not registered_host():
            install_host_in_ayon()
            data_loader()
        return AYONMenus()


enable_python_debugger()
