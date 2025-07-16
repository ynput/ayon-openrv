import logging
import os
import sys
from pathlib import Path

import rv.commands
import rv.qtutils
from qtpy import QtCore, QtWidgets, QtWebEngineWidgets, QtWebChannel

from rv.rvtypes import MinorMode

import ayon_api
from proxy_server import start_proxy_server


LOG_LEVEL = logging.DEBUG


class AYONFeed(QtWidgets.QWidget):
    """Feed widget containing QWebEngineView with React frontend."""
    bridge = None

    def __init__(self, parent=None):
        super().__init__(parent)
        self.log = logging.getLogger("AYONFeed")
        self.log.setLevel(LOG_LEVEL)
        self.con = ayon_api.get_server_api_connection()
        self.local_server = None
        self.server_port = None

        if fe_bridge_path := os.getenv("AYON_FEED_FRONTEND_PYTHON"):
            self.log.info(f"Using frontend bridge from {fe_bridge_path}")
            sys.path.append(fe_bridge_path)
            from ayon_feed_frontend_bridge_openrv import AYONFeedFrontendBridge
            self.bridge = AYONFeedFrontendBridge()
        else:
            from frontend_bridge import PyBridge
            self.bridge = PyBridge()


        self.setup_ui()
        self.setup_webchannel()
        self.load_frontend()

    def setup_ui(self):
        """Setup the widget UI with QWebEngineView."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Create web engine view
        self.web_view = QtWebEngineWidgets.QWebEngineView()
        layout.addWidget(self.web_view)

        # Set minimum size
        self.setMinimumSize(300, 400)

    def setup_webchannel(self):
        """Setup QWebChannel for Python-JavaScript communication."""
        self.channel = QtWebChannel.QWebChannel()
        self.channel.registerObject("pyBridge", self.bridge)

        # Set the web channel on the page
        self.web_view.page().setWebChannel(self.channel)

    def load_frontend(self):
        """Load the React frontend via local HTTP server."""
        # Get the frontend build directory based on mode

        try:
            frontend_resources_env = os.environ.get(
                "AYON_FEED_FRONTEND")
            if not frontend_resources_env:
                raise ValueError(
                    "AYON_FEED_FRONTEND environment variable not set")
            frontend_resources = Path(frontend_resources_env)

            frontend_build = frontend_resources / "index.html"
            self.log.debug(f"Loading frontend from: {frontend_build}")

            # Read configuration from environment variables or use defaults
            ayon_server_url = os.environ.get("AYON_SERVER_URL", "http://localhost:5000")
            ayon_api_key = os.environ.get("AYON_API_KEY", "")

            # Parse URL to get host and port if needed
            target_host = ayon_server_url if ayon_server_url else None

            # Configure authentication headers if API key is provided
            auth_headers = {}
            if ayon_api_key:
                if ayon_api.is_service_user():
                    auth_headers["X-Api-Key"] = ayon_api_key
                else:
                    auth_headers["Authorization"] = f"Bearer {ayon_api_key}"
                self.log.debug("Configured authentication headers for proxy")

            self.log.debug(f"auth_headers: {auth_headers}")
            if frontend_build.exists():
                # Start proxy server to serve the React app
                try:
                    # Start proxy server with dynamic port
                    self.local_server = start_proxy_server(
                        host="localhost",
                        port=0,  # Let system choose available port
                        serve_directory=frontend_resources,
                        proxy_paths=["/api", "/graphql"],  # Configure proxy paths if needed
                        target_host=target_host,  # Set to actual API server if needed
                        auth_headers=auth_headers,  # Pass authentication headers
                        daemon=True
                    )

                    # Get the actual port from the server
                    self.server_port = self.local_server.server.server_address[1]

                    # Load from local HTTP server
                    url = f"http://localhost:{self.server_port}/index.html"
                    self.log.info(f"Loading frontend from proxy server: {url}")
                    self.web_view.load(QtCore.QUrl(url))

                    # Initialize frame after loading
                    QtCore.QTimer.singleShot(1000, self.initialize_frame)

                except Exception as e:
                    self.log.error(f"Failed to start proxy server: {e}")
                    # Fallback to file:// protocol
                    url = QtCore.QUrl.fromLocalFile(str(frontend_build.absolute()))
                    self.web_view.load(url)
                    self.log.info(f"Loaded frontend from file: {frontend_build}")
                    QtCore.QTimer.singleShot(1000, self.initialize_frame)
            else:
                # Fallback: load development server or show error
                self.load_fallback_content()

        except Exception as e:
            self.log.error(f"Failed to load frontend: {e}")
            self.load_fallback_content()

    def initialize_frame(self):
        """Initialize current frame from OpenRV."""
        try:
            current_frame = rv.commands.frame()
            self.bridge.onFrameChanged()
            self.log.info(f"Initialized frame to: {current_frame}")
        except Exception as e:
            self.log.error(f"Failed to initialize frame: {e}")

    def closeEvent(self, event):
        """Clean up resources when widget is closed."""
        if self.local_server:
            try:
                self.local_server.stop()
                self.log.info("Proxy server shut down")
            except Exception as e:
                self.log.error(f"Error shutting down proxy server: {e}")
        super().closeEvent(event)

    def load_fallback_content(self):
        """Load fallback content if React build is not available."""
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>AYON Feed</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    background: #2a2a2a;
                    color: white;
                    padding: 20px;
                    margin: 0;
                }
                button {
                    padding: 10px 20px;
                    background: #0078d4;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    cursor: pointer;
                }
                button:hover { background: #106ebe; }
                input {
                    padding: 8px;
                    margin: 10px 0;
                    background: #333;
                    color: white;
                    border: 1px solid #555;
                    border-radius: 4px;
                    width: 200px;
                }
            </style>
        </head>
        <body>
            <h2>AYON Feed</h2>
            <p>React frontend not built. Using fallback interface.</p>
            <div>
                <input type="text" id="annotationText" value="annotation here" placeholder="Enter annotation...">
                <br>
                <button onclick="addAnnotation()">Add Annotation</button>
            </div>
            <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
            <script>
                let pyBridge = null;

                new QWebChannel(qt.webChannelTransport, function(channel) {
                    pyBridge = channel.objects.pyBridge;
                });

                function addAnnotation() {
                    const text = document.getElementById('annotationText').value;
                    if (pyBridge && text.trim()) {
                        pyBridge.addAnnotation(text);
                        alert('Annotation added: ' + text);
                    }
                }
            </script>
        </body>
        </html>
        """
        self.web_view.setHtml(html_content)
        self.log.warning(
            "Using fallback HTML content - React frontend not available")

    def update_frame(self):
        """Update current frame in the bridge."""
        # Use QTimer to defer the frame query slightly to ensure
        # RV state is updated
        QtCore.QTimer.singleShot(10, self._delayed_frame_update)

    def _delayed_frame_update(self):
        """Update current frame in the bridge."""
        try:
            current_frame = rv.commands.frame()
            self.bridge.onFrameChanged()
            self.log.info(f"Frame changed {current_frame}")
        except Exception as e:
            self.log.error(f"Failed to initialize frame: {e}")


class AYONFeedMode(MinorMode):
    """MinorMode for AYON feed integration."""

    def __init__(self):
        """Initialize the minor mode."""
        MinorMode.__init__(self)
        self.log = logging.getLogger("AYONFeedMode")
        self.log.setLevel(LOG_LEVEL)
        self.panel_widget = None
        self.dock_widget = None

        bindings = [
            (
                "frame-changed",
                self.on_frame_changed,
                "Update feed on frame change"
            ),
            (
                "graph-state-change",
                self._graph_state_change,
                "Handle annotation creation"
            ),
        ]

        menu = [
            ("AYON", [
                ("_", None),
                ("Feed", self.show_ayon_feed, None, None)
            ])
        ]

        self.init(
            "py-ayon-feed-mode",
            bindings,
            None,
            menu,
            # initialization order
            sortKey="source_setup",
            ordering=20,
        )

        self.log.info("AYON Feed mode initialized")

    def get_view_source(self):
        try:
            sources = rv.commands.sourcesAtFrame(rv.commands.frame())
            current_loaded_viewnode = (
                sources[0] if sources and len(sources) > 0 else None)
        except Exception as e:
            self.log.error(f"Error getting sources: {e}")
        return current_loaded_viewnode

    def _graph_state_change(self, event):
        node = self.get_view_source()
        content = event.contents()

        # make sure we have the content and it is in the expected format
        # and that the panel widget is initialized
        if (
            not content
            or ":" not in content
            or ".pen:" not in content
            or self.panel_widget is None
            or "bridge" not in dir(self.panel_widget)
            or not hasattr(
                self.panel_widget.bridge, "generateAnnotationThumbnail")
        ):
            return

        current_attributes = dict(rv.commands.getCurrentAttributes())
        frame_number = rv.commands.frame()
        current_frame = current_attributes.get("SourceFrame", frame_number)

        self.log.debug(
            f"_graph_state_change: "
            f"node={node} "
            f"| event={event.name()} "
            f"| {content} "
            f"| current_frame={current_frame} "
        )

        # Extract the annotation type and content
        self.panel_widget.bridge.generateAnnotationThumbnail(current_frame)


    def show_ayon_feed(self, arg1=None, arg2=None):
        """Show the feed in a dockable widget."""
        try:
            main_window = rv.qtutils.sessionWindow()

            if self.dock_widget is None:
                # Create the panel widget
                self.panel_widget = AYONFeed()

                # Create dock widget
                self.dock_widget = QtWidgets.QDockWidget(
                    "AYON Feed", main_window)
                self.dock_widget.setWidget(self.panel_widget)
                self.dock_widget.setFeatures(
                    QtWidgets.QDockWidget.DockWidgetMovable |
                    QtWidgets.QDockWidget.DockWidgetFloatable |
                    QtWidgets.QDockWidget.DockWidgetClosable
                )

                # Add to main window
                main_window.addDockWidget(
                    QtCore.Qt.RightDockWidgetArea, self.dock_widget)

            # Show the dock widget
            self.dock_widget.show()
            self.dock_widget.raise_()

            self.log.info("AYON Feed shown")
            self.on_frame_changed(None)

        except Exception as e:
            self.log.error(f"Failed to show AYON Feed: {e}")

    def on_frame_changed(self, event=None):
        """Handle frame change events."""
        self.log.debug("Feed: Frame changed")
        if self.panel_widget:
            try:
                self.panel_widget.update_frame()
            except Exception as e:
                self.log.error(f"Failed to update frame in AYON Feed: {e}")


def createMode():
    """Create and return the minor mode instance."""
    return AYONFeedMode()
