import os
import json
import sys
import importlib
import traceback
from functools import partial

import rv.qtutils
from rv.rvtypes import MinorMode

from ayon_api import get_representations

from ayon_core.tools.utils import host_tools
from ayon_core.pipeline import (
    registered_host,
    install_host,
    discover_loader_plugins,
    load_container,
    get_current_project_name,
)
from ayon_core.settings import get_project_settings
from ayon_openrv.api import OpenRVHost
from ayon_openrv.networking import LoadContainerHandler

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


def install_host_in_ayon():
    host = OpenRVHost()
    install_host(host)


class AYONMenus(MinorMode):

    def __init__(self):
        MinorMode.__init__(self)
        self.init(
            name="py-ayon",
            globalBindings=None,
            overrideBindings=[
                # event name, callback, description
                ("ayon_load_container", on_ayon_load_container, "Loads an AYON representation into the session.")
            ],
            menu=[
                # Menu name
                # NOTE: If it already exists it will merge with existing
                # and add submenus / menuitems to the existing one
                ("AYON", self.menu_item()),
            ],
            # initialization order
            sortKey="source_setup",
            ordering=15
        )

    @property
    def _parent(self):
        return rv.qtutils.sessionWindow()

    def load(self, event):
        host_tools.show_loader(parent=self._parent, use_context=True)

    def publish(self, event):
        host_tools.show_publisher(parent=self._parent,
                                  tab="publish")

    def workfiles(self, event):
        host_tools.show_workfiles(parent=self._parent)

    def scene_inventory(self, event):
        host_tools.show_scene_inventory(parent=self._parent)

    def library(self, event):
        host_tools.show_library_loader(parent=self._parent)

    def open_desktop_review_panel(self, panel_name: str, event):
        panel = self.review_controller.get_panel(panel_name)
        self.review_controller.set_project(get_current_project_name())
        self.review_controller.load_ayon_data()
        label = panel_name.replace("_", " ").capitalize()
        self.review_controller.set_docker_widget(self._parent, panel, label)

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
        for panel_name in self.review_controller.get_available_panels():
            label = panel_name.replace("_", " ").capitalize()
            menu.append(
                (
                    f"{label}...",
                    partial(self.open_desktop_review_panel, panel_name),
                    None,
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
        return menu


def data_loader():
    incoming_data_file = os.environ.get(
        "AYON_LOADER_REPRESENTATIONS", None
    )
    if incoming_data_file:
        with open(incoming_data_file, 'rb') as file:
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
    Loader = next(loader for loader in available_loaders
                  if loader.__name__ == "FramesLoader")

    representations = get_representations(project_name,
                                          representation_ids=dataset)

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


def set_docker_widget(parent, panel, widget_name):
    from qtpy import QtWidgets, QtCore
    from ayon_ui_qt import style_widget_and_siblings

    dock = QtWidgets.QDockWidget(widget_name, parent)
    dock.setWidget(panel)
    parent.addDockWidget(QtCore.Qt.RightDockWidgetArea, dock)
    style_widget_and_siblings(dock)
    dock.show()
