# review code
import logging
from collections import OrderedDict
from pathlib import Path

import rv.commands
import rv.qtutils
from ayon_openrv.api import review
from PySide2 import QtCore, QtGui, QtWidgets
from rv.rvtypes import MinorMode


def get_cycle_frame(frame=None, frames_lookup=None, direction="next"):
    """Return nearest frame in direction in frames lookup.

    If the nearest frame in that direction does not exist then cycle
    over to the frames taking the first entry at the other end.

    Note:
        This function can return None if there are no frames to lookup in.

    Args:
        frame (int): frame to search from
        frames_lookup (list): frames to search in.
        direction (str, optional): search direction, either "next" or "prev"
            Defaults to "next".

    Returns:
        int or None: The nearest frame number in that direction or None
            if no lookup frames were passed.

    """
    if direction not in {"prev", "next"}:
        raise ValueError("Direction must be either 'next' or 'prev'. "
                         "Got: {}".format(direction))

    if not frames_lookup:
        return

    elif len(frames_lookup) == 1:
        return frames_lookup[0]

    # We require the sorting of the lookup frames because we pass e.g. the
    # result of `rv.extra_commands.findAnnotatedFrames()` as lookup frames
    # which according to its documentations states:
    # The array is not sorted and some frames may appear more than once.
    frames_lookup = list(sorted(frames_lookup))
    if direction == "next":
        # Return next nearest number or cycle to the lowest number
        return next((i for i in frames_lookup if i > frame),
                    frames_lookup[0])
    elif direction == "prev":
        # Return previous nearest number or cycle to the highest number
        return next((i for i in reversed(frames_lookup) if i < frame),
                    frames_lookup[-1])


class ReviewMenu(MinorMode):
    """Review menu for viewing and annotating frames with status and comments.

    Creates a dockable widget for RV adding review specific functionality like
    status management, commenting, and frame annotations. It attaches to
    the AYON menu and provides controls for navigating through annotated
    frames and managing review metadata.

    The widget displays:
    - Shot name and status
    - Review comment field
    - Annotation navigation controls
    - Image export functionality

    It stores review status and comments as metadata on the source node using
    the AYON attribute prefix. The widget is designed to be used in
    conjunction with the AYON pipeline.
    """

    def __init__(self) -> None:
        MinorMode.__init__(self)
        self.log = logging.getLogger("ReviewMenu")
        self.log.setLevel(logging.INFO)

        self.init(
            "py-ReviewMenu-mode",
            None,
            None,
            [
                (
                    "AYON",
                    [
                        ("_", None),  # separator
                        ("Review", self.runme, None, self._is_active),
                    ],
                )
            ],
            # initialization order
            sortKey="source_setup",
            ordering=20,
        )

        # spacers
        self.verticalSpacer = QtWidgets.QSpacerItem(
            20, 40,
            QtWidgets.QSizePolicy.Minimum,
            QtWidgets.QSizePolicy.Expanding
        )
        self.verticalSpacerMin = QtWidgets.QSpacerItem(
            2, 2,
            QtWidgets.QSizePolicy.Minimum,
            QtWidgets.QSizePolicy.Minimum
        )
        self.horizontalSpacer = QtWidgets.QSpacerItem(
            40, 10,
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Minimum
        )
        self.customDockWidget = QtWidgets.QWidget()

        # data
        self.current_loaded_viewnode = None
        self.review_main_layout = QtWidgets.QVBoxLayout()
        self.rev_head_label = QtWidgets.QLabel("Shot Review")
        self.set_item_font(self.rev_head_label, size=16)
        self.rev_head_name = QtWidgets.QLabel("Shot Name")
        self.current_loaded_shot = QtWidgets.QLabel("")
        self.current_shot_status = QtWidgets.QComboBox()
        self.current_shot_status.addItems([
            "In Review", "Ready For Review", "Reviewed", "Approved", "Deliver"
        ])
        self.current_shot_comment = QtWidgets.QPlainTextEdit()
        self.current_shot_comment.setStyleSheet(
            "color: white; background-color: black"
        )

        self.review_main_layout_head = QtWidgets.QVBoxLayout()
        self.review_main_layout_head.addWidget(self.rev_head_label)
        self.review_main_layout_head.addWidget(self.rev_head_name)
        self.review_main_layout_head.addWidget(self.current_loaded_shot)
        self.review_main_layout_head.addWidget(self.current_shot_status)
        self.review_main_layout_head.addWidget(self.current_shot_comment)

        self.get_view_image = QtWidgets.QPushButton("Export frame as image")
        self.review_main_layout_head.addWidget(self.get_view_image)

        self.remove_cmnt_status_btn = QtWidgets.QPushButton("Remove comment and status")  # noqa
        self.review_main_layout_head.addWidget(self.remove_cmnt_status_btn)

        self.rvWindow = None
        self.dockWidget = None

        # annotations controls
        self.notes_layout = QtWidgets.QVBoxLayout()
        self.notes_layout_label = QtWidgets.QLabel("Annotations")
        self.btn_note_prev = QtWidgets.QPushButton("Previous Annotation")
        self.btn_note_next = QtWidgets.QPushButton("Next Annotation")
        self.notes_layout.addWidget(self.notes_layout_label)
        self.notes_layout.addWidget(self.btn_note_prev)
        self.notes_layout.addWidget(self.btn_note_next)

        self.review_main_layout.addLayout(self.review_main_layout_head)
        self.review_main_layout.addLayout(self.notes_layout)
        self.review_main_layout.addStretch(1)
        self.customDockWidget.setLayout(self.review_main_layout)

        # signals
        self.current_shot_status.currentTextChanged.connect(self.setup_combo_status)  # noqa
        self.current_shot_comment.textChanged.connect(self.comment_update)
        self.get_view_image.clicked.connect(self.get_gui_image)
        self.remove_cmnt_status_btn.clicked.connect(self.clean_cmnt_status)
        self.btn_note_prev.clicked.connect(self.annotate_prev)
        self.btn_note_next.clicked.connect(self.annotate_next)

    def runme(self, arg1=None, arg2=None):
        self.rvWindow = rv.qtutils.sessionWindow()
        if self.dockWidget is None:
            # Create DockWidget and add the Custom Widget on first run
            self.dockWidget = QtWidgets.QDockWidget("AYON Review",
                                                    self.rvWindow)
            self.dockWidget.setWidget(self.customDockWidget)

            # Dock widget to the RV MainWindow
            self.rvWindow.addDockWidget(QtCore.Qt.RightDockWidgetArea,
                                        self.dockWidget)

            self.setup_listeners()
            self.on_frame_changed(None)
        else:
            # Toggle visibility state
            self.dockWidget.toggleViewAction().trigger()
            self.on_frame_changed(None)

    def _is_active(self):
        if self.dockWidget is not None and self.dockWidget.isVisible():
            return rv.commands.CheckedMenuState
        else:
            return rv.commands.UncheckedMenuState

    def set_item_font(self, item, size=14, noweight=False, bold=True):
        font = QtGui.QFont()
        if bold:
            font.setFamily("Arial Bold")
        else:
            font.setFamily("Arial")
        font.setPointSize(size)
        font.setBold(True)
        if not noweight:
            font.setWeight(75)
        item.setFont(font)

    def setup_listeners(self):
        """ Setup listeners for events in RV.

        more information:
            https://aswf-openrv.readthedocs.io/en/latest/rv-manuals/rv-reference-manual/rv-reference-manual-chapter-five.html

        Some other supported signals:
        - new-node
        - graph-state-change
        - before-graph-view-change
        - after-graph-view-change
        - after-progressive-loading
        - range-changed
        - media-relocated
        - source-group-activated
        - after-graph-view-change
        - source-modified
        - source-media-set
        - source-media-rep-activated
        - incoming-source-path
        - source-media-rep-activated
        - before-session-deletion
        - session-initialized
        - after-progressive-loading
        - margins-changed
        - mark-frame
        - unmark-frame
        """
        # frame-changed event
        rv.commands.bind(
            "default", "global", "frame-changed",
            self.on_frame_changed, "Update UI on frame change",
        )
        # new-source event
        rv.commands.bind(
            "default", "global", "new-source",
            self.update_ui_attribs, "Update UI on new source",
        )
        # graph-node-inputs-changed
        rv.commands.bind(
            "default", "global", "graph-node-inputs-changed",
            self.graph_change, "Update UI on graph node inputs changed",
        )

    def on_frame_changed(self, event):
        """Handler for when the active clip/source changes"""
        if event is not None:
            # If the event is not None, it means the frame has changed
            self.log.debug(f"on_frame_changed: event={event.name()} | {event.contents()}")

        # Get the new active source/clip
        self.get_view_source()

        # Update the UI to reflect the new clip
        self.update_ui_attribs()

    def graph_change(self, event):
        self.log.debug("graph_change")
        # Get the new active source/clip
        self.get_view_source()

        # Update the UI to reflect the new clip
        self.update_ui_attribs()

    def get_view_source(self):
        try:
            sources = rv.commands.sourcesAtFrame(rv.commands.frame())
            self.current_loaded_viewnode = (
                sources[0] if sources and len(sources) > 0 else None)
            self.log.debug(f"get_view_source: {self.current_loaded_viewnode}")
        except Exception as e:
            self.log.error(f"Error getting sources: {e}")
            self.current_loaded_viewnode = None

    def update_ui_attribs(self):
        node = self.current_loaded_viewnode
        self.log.debug(f"update_ui_attribs: {node}")
        # Use namespace as loaded shot label
        namespace = ""
        if node is not None:
            property_name = f"{node}.{review.AYON_ATTR_PREFIX}namespace"
            self.log.debug(f"property_name: {property_name}")
            if rv.commands.propertyExists(property_name):
                namespace = rv.commands.getStringProperty(property_name)[0]

        self.current_loaded_shot.setText(namespace)

        self.setup_properties()
        self.get_comment()

    def setup_combo_status(self):
        # setup properties
        node = self.current_loaded_viewnode
        self.log.debug(f"setup_combo_status: {node}")
        if node is None:
            return

        att_prop = f"{node}.{review.AYON_ATTR_PREFIX}task_status"
        status = self.current_shot_status.currentText()

         # Check if property exists, create it if it doesn't
        if not rv.commands.propertyExists(att_prop):
            rv.commands.newProperty(att_prop, rv.commands.StringType, 1)

        rv.commands.setStringProperty(att_prop, [str(status)], True)
        self.current_shot_comment.setFocus()

        self.current_shot_status.setCurrentText(status)

    def setup_properties(self):
        # setup properties
        node = self.current_loaded_viewnode
        self.log.debug(f"setup_properties: {node}")
        if node is None:
            self.current_shot_status.setCurrentIndex(0)
            return

        att_prop = f"{node}.{review.AYON_ATTR_PREFIX}task_status"
        if not rv.commands.propertyExists(att_prop):
            status = "In Review"
            rv.commands.newProperty(att_prop, rv.commands.StringType, 1)
            rv.commands.setStringProperty(att_prop, [str(status)], True)
            self.current_shot_status.setCurrentIndex(0)
        else:
            status = rv.commands.getStringProperty(att_prop)[0]
            self.current_shot_status.setCurrentText(status)

    def comment_update(self):
        node = self.current_loaded_viewnode
        self.log.debug(f"comment_update: {node}")
        if node is None:
            return

        comment = self.current_shot_comment.toPlainText()
        att_prop = f"{node}.{review.AYON_ATTR_PREFIX}task_comment"
        rv.commands.newProperty(att_prop, rv.commands.StringType, 1)
        rv.commands.setStringProperty(att_prop, [str(comment)], True)

    def get_comment(self):
        node = self.current_loaded_viewnode
        self.log.debug(f"get_comment: {node}")
        if node is None:
            self.current_shot_comment.setPlainText("")
            return

        att_prop = f"{node}.{review.AYON_ATTR_PREFIX}task_comment"
        if not rv.commands.propertyExists(att_prop):
            rv.commands.newProperty(att_prop, rv.commands.StringType, 1)
            rv.commands.setStringProperty(att_prop, [""], True)
        else:
            status = rv.commands.getStringProperty(att_prop)[0]
            self.current_shot_comment.setPlainText(status)

    def clean_cmnt_status(self):
        node = self.current_loaded_viewnode
        self.log.debug(f"clean_cmnt_status: {node}")

        for prop in [
            f"{node}.{review.AYON_ATTR_PREFIX}task_comment",
            f"{node}.{review.AYON_ATTR_PREFIX}task_status",
        ]:
            self.log.debug(f"prop: {prop}")
            if not rv.commands.propertyExists(prop):
                rv.commands.newProperty(prop, rv.commands.StringType, 1)
            rv.commands.setStringProperty(prop, [""], True)

        self.current_shot_status.setCurrentText("In Review")
        self.current_shot_comment.setPlainText("")

    def get_gui_image(self, filename=None):
        current_attributes = OrderedDict(rv.commands.getCurrentAttributes())
        frame_number = rv.commands.frame()
        current_frame = current_attributes.get("SourceFrame", frame_number)
        current_file_path = Path(current_attributes.get("File", "Image.png"))

        current_frame_name = current_file_path.stem
        if current_frame not in current_frame_name:
            current_frame_name = f"{current_frame_name}.{current_frame}"

        if not filename:
            # Allow user to pick filename
            filename, _ = QtWidgets.QFileDialog.getSaveFileName(
                self.customDockWidget,
                "Save image",
                f"annotate_{current_frame_name}.png",
                "Images (*.png *.jpg *.jpeg *.exr)"
            )
            if not filename:
                # User cancelled
                return

        rv.commands.exportCurrentFrame(filename)
        print("Current frame exported to: {}".format(filename))

    def annotate_next(self):
        """Set frame to next annotated frame"""
        all_notes = self.get_annotated_for_view()
        if not all_notes:
            return
        nxt = get_cycle_frame(frame=rv.commands.frame(),
                              frames_lookup=all_notes,
                              direction="next")

        rv.commands.setFrame(int(nxt))
        rv.commands.redraw()

    def annotate_prev(self):
        """Set frame to previous annotated frame"""
        all_notes = self.get_annotated_for_view()
        if not all_notes:
            return
        previous = get_cycle_frame(frame=rv.commands.frame(),
                                   frames_lookup=all_notes,
                                   direction="prev")
        rv.commands.setFrame(int(previous))
        rv.commands.redraw()

    def get_annotated_for_view(self):
        """Return the frame numbers for all annotated frames"""
        annotated_frames = rv.extra_commands.findAnnotatedFrames()
        return annotated_frames

    def get_task_status(self):
        import ftrack_api
        session = ftrack_api.Session(auto_connect_event_hub=False)
        self.log.debug("Ftrack user: \"{0}\"".format(session.api_user))

def createMode():
    return ReviewMenu()
