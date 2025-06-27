import logging
import os
from pathlib import Path
import zipfile
import tempfile

import rv.commands
import rv.qtutils
from PySide2 import QtCore, QtWidgets, QtWebEngineWidgets, QtWebChannel

from rv.rvtypes import MinorMode
from ayon_core.lib import is_dev_mode_enabled
from ayon_openrv.constants import AYON_ATTR_PREFIX

import ayon_api
from proxy_server import start_proxy_server


LOG_LEVEL = logging.DEBUG


class PyBridge(QtCore.QObject):
    """Python bridge object for QWebChannel communication."""

    # Change from dict to individual parameters for better QWebChannel serialization
    frameChanged = QtCore.Signal(int, str, str, str)

    def __init__(self):
        super().__init__()
        self.log = logging.getLogger("PyBridge")
        self.log.setLevel(LOG_LEVEL)
        self.current_project = None
        self.current_version_id = None
        self.con = None
        try:
            self.con = ayon_api.get_server_api_connection()
        except Exception as e:
            self.log.warning(f"Failed to get AYON API connection: {e}")

    @QtCore.Slot(result=int)
    def getCurrentFrame(self):
        """Get current frame number."""

        try:
            current_frame = rv.commands.frame()
            return current_frame
        except Exception as e:
            self.log.error(f"Failed to get current frame: {e}")
            return 0

    @QtCore.Slot(result=str)
    def getProjectName(self):
        """Get current project name."""
        try:
            # Try to get from current source attributes
            current_frame = rv.commands.frame()
            sources = rv.commands.sourcesAtFrame(current_frame)
            if sources:
                current_node = sources[0]
                project_attr = f"{current_node}.{AYON_ATTR_PREFIX}projectName"
                if rv.commands.propertyExists(project_attr):
                    project_name = rv.commands.getStringProperty(project_attr)[0]
                    self.current_project = project_name
                    self.log.info(f"Captured project name: {self.current_project}")
                    return project_name

            # Fallback to environment variable
            project_name = os.environ.get('AYON_PROJECT_NAME', '')
            self.current_project = project_name
            self.log.info(f"Env project name: {self.current_project}")
            return project_name
        except Exception as e:
            self.log.error(f"Failed to get project name: {e}")
            return ''

    @QtCore.Slot(result=str)
    def getVersionId(self):
        """Get current project name."""
        try:
            # Try to get from current source attributes
            current_frame = rv.commands.frame()
            sources = rv.commands.sourcesAtFrame(current_frame)
            if sources:
                current_node = sources[0]
                version_attr = f"{current_node}.{AYON_ATTR_PREFIX}versionId"
                if rv.commands.propertyExists(version_attr):
                    version_id = rv.commands.getStringProperty(version_attr)[0]
                    self.current_version_id = version_id
                    self.log.info(f"Captured version id: {self.current_version_id}")
                    return version_id

        except Exception as e:
            self.log.error(f"Failed to get version id: {e}")
            return ''

    @QtCore.Slot(result=str)
    def getUserName(self):
        """Get current user name."""
        try:
            # Try to get from AYON API connection
            if hasattr(self, 'con') and self.con:
                user_info = self.con.get_user()
                if user_info and 'name' in user_info:
                    return user_info['name']

            # Fallback to environment variable
            return os.environ.get('AYON_USER_NAME', os.environ.get('USER', 'unknown'))
        except Exception as e:
            self.log.error(f"Failed to get user name: {e}")
            return 'unknown'

    @QtCore.Slot(result=dict)
    def onFrameChanged(self):
        """Register callback for frame changes.

        Placeholder for JS callback registration.
        """
        # This is handled by the frameChanged signal in QWebChannel
        # The React app will connect to this signal automatically
        current_frame = self.getCurrentFrame()
        project_name = self.getProjectName()
        version_id = self.getVersionId()
        user_name = self.getUserName()

        # Log the data for debugging
        context_data = {
            'currentFrame': current_frame,
            'projectName': project_name,
            'versionId': version_id,
            'userName': user_name,
        }
        self.log.info(f"Frame changed: {context_data}")

        # Emit signal with individual parameters instead of a dictionary
        # Order: currentFrame, projectName, versionId, userName
        self.frameChanged.emit(current_frame, project_name, version_id, user_name)


    @QtCore.Slot(str)
    def addAnnotation(self, text):
        """Add annotation to current frame and submit to AYON."""
        try:
            current_frame = rv.commands.frame()

            # Get current source
            sources = rv.commands.sourcesAtFrame(current_frame)
            current_node = (
                sources[0] if sources and len(sources) > 0 else None)
            if not current_node:
                self.log.warning("No sources available for annotation")
                return

            # Generate thumbnail for the annotation
            thumbnail_path = self._generate_frame_thumbnail(current_frame)

            # Create annotation data
            annotation_data = {
                'frame': current_frame,
                'text': text,
                'thumbnail': thumbnail_path,
                'timestamp': rv.commands.frame() / rv.commands.fps()
            }

            # Store annotation locally on source node
            local_attr_name = f"{AYON_ATTR_PREFIX}annotations"
            try:
                existing_annotations = rv.commands.getStringProperty(f"{current_node}.{local_attr_name}")
                annotations_list = eval(existing_annotations[0]) if existing_annotations else []
            except:
                annotations_list = []

            annotations_list.append(annotation_data)
            rv.commands.setStringProperty(
                f"{current_node}.{local_attr_name}",
                [str(annotations_list)],
                True  # persistent
            )

            # Submit to AYON server (placeholder for actual API call)
            ayon_activity_id = self._submit_to_ayon_feed(annotation_data)

            if ayon_activity_id:
                # Store AYON activity ID as attribute
                ayon_id_attr = f"{AYON_ATTR_PREFIX}activity_id_{current_frame}"
                rv.commands.setStringProperty(
                    f"{current_node}.{ayon_id_attr}",
                    [ayon_activity_id],
                    True
                )

            self.log.info(f"Added annotation for frame {current_frame}: {text}")

        except Exception as e:
            self.log.error(f"Failed to add annotation: {e}")

    def _generate_frame_thumbnail(self, frame):
        """Generate thumbnail for the current frame."""
        try:
            temp_dir = Path(tempfile.mkdtemp(prefix="ayon_rv_thumb_"))
            thumbnail_path = temp_dir / f"frame_{frame}.jpg"

            # Save current frame as thumbnail using RV API
            current_frame = rv.commands.frame()
            rv.commands.setFrame(frame)

            # Export current frame as image
            rv.commands.writeImage(str(thumbnail_path), frame)

            # Restore original frame
            rv.commands.setFrame(current_frame)

            return str(thumbnail_path)
        except Exception as e:
            self.log.error(f"Failed to generate thumbnail: {e}")
            return None

    def _submit_to_ayon_feed(self, annotation_data):
        """Submit annotation to AYON server feed."""
        try:
            # Get AYON server credentials from environment
            server_url = os.environ.get('AYON_SERVER_URL')
            api_key = os.environ.get('AYON_API_KEY')

            if not server_url or not api_key:
                self.log.warning("AYON server credentials not found in environment")
                return None

            # Import ayon_api for server communication
            try:
                import ayon_api
            except ImportError:
                self.log.error("ayon_api not available for server communication")
                return None

            # Create activity data for AYON feed
            activity_data = {
                'activityType': 'comment',
                'body': annotation_data['text'],
                'data': {
                    'frame': annotation_data['frame'],
                    'timestamp': annotation_data['timestamp'],
                    'thumbnail': annotation_data.get('thumbnail')
                }
            }

            # Submit to AYON server using ayon_api
            if self.current_version_id:
                response = ayon_api.post(
                    f"projects/{self.current_project}/versions/{self.current_version_id}/activities",
                    **activity_data
                )

                if response and 'id' in response:
                    activity_id = response['id']
                    self.log.info(f"Submitted annotation to AYON: {activity_id}")
                    return activity_id
            else:
                self.log.warning("No entity or version context available for annotation submission")
                return None

        except Exception as e:
            self.log.error(f"Failed to submit to AYON feed: {e}")
            return None


class AYONFeed(QtWidgets.QWidget):
    """Feed widget containing QWebEngineView with React frontend."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.log = logging.getLogger("AYONFeed")
        self.log.setLevel(LOG_LEVEL)
        self.bridge = PyBridge()
        self.con = ayon_api.get_server_api_connection()
        self.local_server = None
        self.server_port = None

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
        self.log.warning("Using fallback HTML content - React frontend not available")

    def update_frame(self):
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
