import os
import json
import sys
import importlib

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
                ("AYON", [
                    # Menuitem name, actionHook (event), key, stateHook
                    ("Load...", self.load, None, None),
                    ("Publish...", self.publish, None, None),
                    ("Manage...", self.scene_inventory, None, None),
                    ("Library...", self.library, None, None),
                    ("_", None),  # separator
                    ("Work Files...", self.workfiles, None, None),
                ])
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


def data_loader():
    incoming_data_file = os.environ.get(
        "OPENPYPE_LOADER_REPRESENTATIONS", None
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


def createMode():
    # This function triggers for each RV session window being opened, for
    # example when using File > New Session this will trigger again. As such
    # we only want to trigger the startup install when the host is not
    # registered yet.
    if not registered_host():
        install_host_in_ayon()
        data_loader()
    return AYONMenus()
