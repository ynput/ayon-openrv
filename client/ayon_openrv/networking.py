import os
import json
import socket
from time import sleep, time

from ayon_api import (
    get_addon_settings,
    get_representations
)

from ayon_core.pipeline import (
    load_container,
    discover_loader_plugins,
    get_current_project_name,
)

from ayon_openrv.version import __version__
from ayon_openrv.addon import OpenRVAddon

from ayon_core.lib.transcoding import (
    IMAGE_EXTENSIONS, VIDEO_EXTENSIONS
)

from ayon_core.lib import Logger

log = Logger.get_logger(__name__)


class RVConnector:
    addon_settings = get_addon_settings(OpenRVAddon.name, __version__)

    def __init__(self, host: str = None, name: str = None, port: int = None):
        self.host = host or "localhost"
        self.name = name or self.addon_settings["network"]["conn_name"]
        self.port = port or self.addon_settings["network"]["conn_port"]

        self.is_connected = False
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        self.connect()

    def __enter__(self):
        """Enters the context manager."""
        start = time()
        while not self.is_connected:
            if time() - start > self.addon_settings["network"]["timeout"]:
                raise Exception(f"Timeout reached. Tried with {self.host = } "
                                f"{self.port =  } {self.name = }")
            self.connect()
        return self

    def __exit__(self, *args):
        """Exits the context manager."""
        self.close()

    @property
    def message_available(self) -> bool:
        """Checks if a message is available."""
        try:
            msg = self.sock.recv(1, socket.MSG_PEEK)
            if len(msg) > 0:
                return True
        except Exception as err:
            log.error(err, exc_info=True)

        return False

    def connect(self) -> None:
        """Connects to the RV server."""
        log.debug("Connecting with: "
                  f"{self.host = } {self.port = } {self.name = }")
        if self.is_connected:
            return
        self.__connect_socket()

    def send_message(self, message):
        log.debug(f"send_message: {message}")
        if not self.is_connected:
            return

        msg = f"MESSAGE {len(message)} {message}"
        try:
            self.sock.sendall(msg.encode("utf-8"))
        except Exception:
            self.close()

    def send_event(self, eventName, eventContents, shall_return=True):
        """
        Send a remote event, then wait for a return value (string).
        eventName must be one of the events
        listed in the RV Reference Manual.
        """
        message = f"RETURNEVENT {eventName} * {eventContents}"
        self.send_message(message)
        if shall_return:
            return self.__process_events(process_return_only=True)

    def close(self):
        if self.is_connected:
            self.send_message("DISCONNECT")
            timeout = os.environ.get("AYON_RV_SOCKET_CLOSE_TIMEOUT", 100)

            if not isinstance(timeout, int):
                timeout = int(timeout)

            sleep(timeout / 1000) # wait for the message to be sent
        
        self.sock.shutdown(socket.SHUT_RDWR)
        self.sock.close()
        self.is_connected = False

    def receive_message(self):
        msg_type, msg_data = "", None

        try:
            while True:
                char = self.sock.recv(1).decode("utf-8")
                if char == " ":
                    break
                msg_type += char
            msg_data = self.sock.recv(
                len(msg_type)).decode("utf-8")
        except Exception as err:
            log.error(err, exc_info=True)

        return (msg_type, msg_data)

    def __send_initial_greeting(self):
        greeting = f"{self.name} rvController"
        cmd = f"NEWGREETING {len(greeting)} {greeting}"
        try:
            self.sock.sendall(cmd.encode("utf-8"))
        except Exception:
            self.is_connected = False

    def process_message(self, data):
        log.debug(f"process message: {data = }")

    def __process_events(self, process_return_only=False):
        while True:
            sleep(0.01)
            while not self.message_available:
                if not self.is_connected:
                    return ""
                
                if not self.message_available and process_return_only:
                    sleep(0.01)
                else:
                    break

            if not self.message_available:
                break

            # get single message
            resp_type, resp_data = self.receive_message()
            log.debug(f"received message: {resp_type}: {resp_data}")

            if resp_type == "MESSAGE":
                if resp_data == "DISCONNECT":
                    self.is_connected = False
                    self.close()
                    return
                # (event, event_data) = self.process_message()
                self.process_message()

            if resp_type == "PING":
                self.sock.sendall("PONG 1 p".encode("utf-8"))

    def __connect_socket(self):
        try:
            self.sock.connect((self.host, self.port))
            self.__send_initial_greeting()
            self.sock.sendall("PINGPONGCONTROL 1 0".encode("utf-8"))
            self.is_connected = True
        except Exception:
            self.is_connected = False


class LoadContainerHandler:
    def __init__(self, event):
        #? where is the implementation of event
        if event.name() != "ayon_load_container":
            raise Exception(
                f"LoadContainerHandler called on wrong event. {event}"
            )
        self.event = event

    def handle_event(self):
        #! this currently drops support for loading unmanaged containers
        # decode event contents
        event_data: dict = json.loads(self.event.contents())

        # find out which loader type to use for event representation
        ayon_containers = {"FramesLoader": [], "MovLoader": []}
        for node in event_data:
            if not node.get("representation"):
                raise Exception("event data has no representation. "
                                f"{event_data = }")

            for ext in IMAGE_EXTENSIONS:
                ext = ext.lstrip(".")
                if ext in node["objectName"].lower():
                    ayon_containers["FramesLoader"].append(node)
                    break
            for ext in VIDEO_EXTENSIONS:
                ext = ext.lstrip(".")
                if ext in node["objectName"].lower():
                    ayon_containers["MovLoader"].append(node)
                    break

        # load the container with appropriate loader plugin
        # this enables us to use AYON manager for versioning
        if ayon_containers["FramesLoader"]:
            representation_ids = [i["representation"]
                                  for i in ayon_containers["FramesLoader"]]
            log.debug(f"{representation_ids = }")
            load_representations(representation_ids,
                                 loader_type="FramesLoader")
        if ayon_containers["MovLoader"]:
            representation_ids = [i["representation"]
                                  for i in ayon_containers["MovLoader"]]
            log.debug(f"{representation_ids = }")
            load_representations(representation_ids, loader_type="MovLoader")


def load_representations(representation_ids: list[str], loader_type: str):
    """Load representations into current app session."""
    project_name = get_current_project_name()

    available_loaders = discover_loader_plugins(project_name)
    if not loader_type:
        raise ValueError("Loader type not provided. "
                         "Expected 'FramesLoader' or 'MovLoader'.")
    Loader = next(loader for loader in available_loaders
                  if loader.__name__ == loader_type)

    representations = get_representations(project_name,
        representation_ids=representation_ids)

    for representation in representations:
        load_container(Loader, representation, project_name=project_name)
