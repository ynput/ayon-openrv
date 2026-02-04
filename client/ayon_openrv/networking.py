"""Networking module for RV communication.

Provides socket-based communication with RV for remote control
and container loading functionality.
"""

from __future__ import annotations

import json
import os
import socket
from time import sleep, time
from typing import TYPE_CHECKING

from ayon_api import get_addon_settings, get_representations
from ayon_core.lib import Logger
from ayon_core.lib.transcoding import IMAGE_EXTENSIONS, VIDEO_EXTENSIONS
from ayon_core.pipeline import (
    discover_loader_plugins,
    get_current_project_name,
    get_representation_path,
    load_container,
)

from ayon_openrv.addon import OpenRVAddon
from ayon_openrv.version import __version__

if TYPE_CHECKING:
    from typing import Any

log = Logger.get_logger(__name__)


class RVConnector:
    """Manages socket connection to RV for remote control.

    This class provides a context manager interface for connecting
    to RV's network control interface, sending commands, and
    receiving responses.

    Attributes:
        host: The hostname to connect to.
        name: The connection name for identification.
        port: The port to connect to.
        is_connected: Whether currently connected to RV.
    """

    _cached_settings: dict[str, Any] | None = None

    def __init__(
        self,
        host: str | None = None,
        name: str | None = None,
        port: int | None = None,
    ) -> None:
        """Initialize RV connector.

        Args:
            host: Hostname to connect to. Defaults to "localhost".
            name: Connection name. Defaults to value from addon settings.
            port: Port number. Defaults to value from addon settings.
        """
        settings = self._get_settings()

        self.host = host or "localhost"
        self.name = name or settings["network"]["conn_name"]
        self.port = port or settings["network"]["conn_port"]

        self.is_connected = False
        self._sock: socket.socket | None = None

        self._attempts = 0
        self._elapsed = 0.0

        self.connect()

    @classmethod
    def _get_settings(cls) -> dict[str, Any]:
        """Get addon settings with lazy loading.

        Returns:
            The addon settings dictionary.
        """
        if cls._cached_settings is None:
            cls._cached_settings = get_addon_settings(
                OpenRVAddon.name, __version__
            )
        # At this point _cached_settings is guaranteed to be set
        return cls._cached_settings  # type: ignore[return-value]

    def __enter__(self) -> RVConnector:
        """Enter the context manager with retry logic.

        Attempts to connect with exponential backoff until success
        or timeout is reached.

        Returns:
            Self for context manager usage.

        Raises:
            ConnectionError: If connection times out.
        """
        settings = self._get_settings()
        start = time()
        self._attempts = 0
        timeout = float(settings["network"]["timeout"])

        while not self.is_connected:
            self._elapsed = time() - start
            if self._elapsed > timeout:
                raise ConnectionError(
                    f"Timeout after {self._elapsed:.1f}s connecting to RV. "
                    f"host={self.host}, port={self.port}, name={self.name}"
                )

            # Exponential backoff: 0.1s, 0.2s, 0.4s, ... max 2s
            if self._attempts > 0:
                delay = min(0.1 * (2**self._attempts), 2.0)
                log.debug(
                    f"Retry attempt {self._attempts}, waiting {delay:.2f}s"
                )
                sleep(delay)

            self._attempts += 1
            self.connect()

        return self

    def __exit__(self, *args: Any) -> None:
        """Exit the context manager and close connection."""
        self.close()

    @property
    def sock(self) -> socket.socket:
        """Get the current socket, creating one if needed.

        Returns:
            The socket instance.

        Raises:
            RuntimeError: If no socket is available.
        """
        if self._sock is None:
            raise RuntimeError("Socket not initialized")
        return self._sock

    @property
    def message_available(self) -> bool:
        """Check if a message is available on the socket.

        Returns:
            True if data is available to read, False otherwise.
        """
        if self._sock is None:
            return False

        try:
            msg = self._sock.recv(1, socket.MSG_PEEK)
            return len(msg) > 0
        except socket.timeout:
            return False
        except OSError as err:
            log.error(f"Error checking for message: {err}", exc_info=True)
            return False

    def connect(self) -> None:
        """Connect to the RV server.

        Creates a new socket and attempts connection. If already
        connected, does nothing.
        """
        if self.is_connected:
            return
        log.debug(
            f"Connecting with: host={self.host}, "
            f"port={self.port}, name={self.name} "
            f"attempt {self._attempts}"
        )
        self._connect_socket()

    def send_message(self, message: str) -> None:
        """Send a message to RV.

        Args:
            message: The message string to send.
        """
        log.debug(f"send_message: {message}")
        if not self.is_connected or self._sock is None:
            return

        msg = f"MESSAGE {len(message)} {message}"
        try:
            self._sock.sendall(msg.encode("utf-8"))
        except OSError:
            self.close()

    def send_event(
        self,
        event_name: str,
        event_contents: str,
        shall_return: bool = True,
    ) -> str:
        """Send a remote event and optionally wait for return value.

        Args:
            event_name: Event name from RV Reference Manual.
            event_contents: Event payload data.
            shall_return: Whether to wait for a return value.

        Returns:
            The return value string, or empty string if not waiting.
        """
        message = f"RETURNEVENT {event_name} * {event_contents}"
        self.send_message(message)
        if shall_return:
            return self._process_events(process_return_only=True)
        return ""

    def close(self) -> None:
        """Close the connection and clean up resources."""
        if self.is_connected and self._sock is not None:
            try:
                self.send_message("DISCONNECT")
                timeout = int(
                    os.environ.get("AYON_RV_SOCKET_CLOSE_TIMEOUT", 100)
                )
                sleep(timeout / 1000)
            except OSError:
                pass  # Best effort disconnect message

        if self._sock is not None:
            try:
                self._sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass  # Already closed or not connected

            try:
                self._sock.close()
            except OSError:
                pass

            self._sock = None

        self.is_connected = False

    def receive_message(self) -> tuple[str, str | None]:
        """Receive a message from the socket.

        Parses the RV protocol format: TYPE LENGTH DATA

        Returns:
            Tuple of (message_type, message_data). Data may be None
            on error.
        """
        msg_type = ""
        msg_data = None

        if self._sock is None:
            return (msg_type, msg_data)

        try:
            # Read message type until space
            while True:
                char = self._sock.recv(1).decode("utf-8")
                if char == " ":
                    break
                msg_type += char

            # Read message length until space
            length_str = ""
            while True:
                char = self._sock.recv(1).decode("utf-8")
                if char == " ":
                    break
                length_str += char

            # Read the actual message data
            msg_length = int(length_str)
            if msg_length > 0:
                data_bytes = b""
                while len(data_bytes) < msg_length:
                    chunk = self._sock.recv(msg_length - len(data_bytes))
                    if not chunk:
                        break
                    data_bytes += chunk
                msg_data = data_bytes.decode("utf-8")

        except (OSError, ValueError) as err:
            log.error(f"Error receiving message: {err}", exc_info=True)

        return (msg_type, msg_data)

    def _send_initial_greeting(self) -> None:
        """Send the initial greeting to establish connection."""
        if self._sock is None:
            return

        greeting = f"{self.name} rvController"
        cmd = f"NEWGREETING {len(greeting)} {greeting}"
        try:
            self._sock.sendall(cmd.encode("utf-8"))
        except OSError:
            self.is_connected = False

    def process_message(self, data: str | None) -> None:
        """Process a received message.

        Args:
            data: The message data to process.
        """
        log.debug(f"process message: data={data}")

    def _wait_for_message(self, timeout: float = 0.1) -> bool:
        """Wait for a message to become available.

        Args:
            timeout: Maximum time to wait in seconds.

        Returns:
            True if message is available, False otherwise.
        """
        start = time()
        while time() - start < timeout:
            if not self.is_connected:
                return False
            if self.message_available:
                return True
            sleep(0.01)
        return False

    def _process_events(self, process_return_only: bool = False) -> str:
        """Process incoming events from RV.

        Args:
            process_return_only: If True, only process RETURN events
                and return immediately upon receiving one.

        Returns:
            The return value for RETURN events, empty string otherwise.
        """
        while self.is_connected:
            if not self._wait_for_message(timeout=0.1):
                if not process_return_only:
                    break
                continue

            resp_type, resp_data = self.receive_message()
            log.debug(f"Received message: {resp_type}: {resp_data}")

            if resp_type == "MESSAGE":
                if resp_data == "DISCONNECT":
                    self.close()
                    return ""
                self.process_message(resp_data)

            elif resp_type == "PING":
                if self._sock is not None:
                    try:
                        self._sock.sendall(b"PONG 1 p")
                    except OSError:
                        pass

            elif resp_type == "RETURN" and process_return_only:
                return resp_data or ""

        return ""

    def _connect_socket(self) -> None:
        """Create and connect a new socket to RV.

        Creates a fresh socket for each connection attempt to avoid
        reuse issues with failed connections.
        """
        # Close existing socket if any
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

        # Create fresh socket
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.settimeout(5.0)

        try:
            self._sock.connect((self.host, self.port))
            self._send_initial_greeting()
            self._sock.sendall(b"PINGPONGCONTROL 1 0")
            self.is_connected = True
        except OSError as err:
            log.debug(f"Connection failed: {err}")
            self.is_connected = False
            # Clean up failed socket
            if self._sock is not None:
                try:
                    self._sock.close()
                except OSError:
                    pass
                self._sock = None
        else:
            log.info(
                f"Connected with: host={self.host}, "
                f"port={self.port}, name={self.name} "
                f"in {self._elapsed:.1f}sec. after {self._attempts} attempts."
            )


class LoadContainerHandler:
    """Handles loading containers from RV events.

    Processes ayon_load_container events to load representations
    using appropriate loader plugins.
    """

    def __init__(self, event: Any) -> None:
        """Initialize the handler with an event.

        Args:
            event: The RV event to handle.

        Raises:
            ValueError: If event is not an ayon_load_container event.
        """
        if event.name() != "ayon_load_container":
            raise ValueError(
                f"LoadContainerHandler called on wrong event: {event}"
            )
        self.event = event

    def handle_event(self) -> None:
        """Handle the container loading event.

        Loads representations based on their file types using
        appropriate loader plugins.
        """
        event_data: dict = json.loads(self.event.contents())
        project_name = get_current_project_name()

        if project_name is None:
            log.error("No current project name available")
            return

        representation_ids = [
            event["representation"]
            for event in event_data
            if event.get("representation")
        ]
        log.debug(f"representation_ids: {representation_ids}")

        repre_entities = get_representations(
            project_name=project_name, representation_ids=representation_ids
        )

        available_loaders = discover_loader_plugins(project_name)

        frames_loader_plugin = next(
            (
                loader
                for loader in available_loaders
                if loader.__name__ == "FramesLoader"
            ),
            None,
        )
        mov_loader_plugin = next(
            (
                loader
                for loader in available_loaders
                if loader.__name__ == "MovLoader"
            ),
            None,
        )

        if frames_loader_plugin is None:
            log.warning("FramesLoader plugin not found")
        if mov_loader_plugin is None:
            log.warning("MovLoader plugin not found")

        for repre in repre_entities:
            filepath = get_representation_path(repre)
            extension = os.path.splitext(filepath)[1].lstrip(".").lower()

            self._load_by_extension(
                repre,
                extension,
                project_name,
                frames_loader_plugin,
                mov_loader_plugin,
            )

    def _load_by_extension(
        self,
        repre: Any,
        extension: str,
        project_name: str,
        frames_loader: Any | None,
        mov_loader: Any | None,
    ) -> None:
        """Load a representation using the appropriate loader.

        Args:
            repre: The representation entity.
            extension: The file extension (without dot).
            project_name: The current project name.
            frames_loader: The frames loader plugin, if available.
            mov_loader: The mov loader plugin, if available.
        """
        # Check image extensions
        if frames_loader is not None:
            for ext in IMAGE_EXTENSIONS:
                ext = ext.lstrip(".")
                if ext == extension:
                    load_container(
                        frames_loader, repre, project_name=project_name
                    )
                    return

        # Check video extensions
        if mov_loader is not None:
            for ext in VIDEO_EXTENSIONS:
                ext = ext.lstrip(".")
                if ext == extension:
                    load_container(
                        mov_loader, repre, project_name=project_name
                    )
                    return

        log.warning(f"No loader found for extension: {extension}")
