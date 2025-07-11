import logging
import os
from pathlib import Path
import tempfile

import rv.commands
import rv.qtutils
from PySide2 import QtCore

from ayon_openrv.constants import AYON_ATTR_PREFIX

import ayon_api


LOG_LEVEL = logging.DEBUG


class PyBridge(QtCore.QObject):
    """Python bridge object for QWebChannel communication."""

    # Change from dict to individual parameters for better QWebChannel serialization
    frameChanged = QtCore.Signal(int, str, str, str)

    def __init__(self):
        super().__init__()
        self.log = logging.getLogger("PyBridge")
        self.log.setLevel(LOG_LEVEL)


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
