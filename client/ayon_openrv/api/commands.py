import logging

import rv
from ayon_core.pipeline.context_tools import get_current_folder_entity

log = logging.getLogger(__name__)


def reset_frame_range():
    """ Set timeline frame range.
    """
    folder_entity = get_current_folder_entity(fields={"path", "attrib"})
    folder_path = folder_entity["path"]
    folder_attribs = folder_entity["attrib"]

    frame_start = folder_attribs.get("frameStart")
    frame_end = folder_attribs.get("frameEnd")

    if frame_start is None or frame_end is None:
        log.warning("No edit information found for {}".format(folder_path))
        return

    rv.commands.setFrameStart(frame_start)
    rv.commands.setFrameEnd(frame_end)
    rv.commands.setFrame(frame_start)


def set_session_fps():
    """ Set session fps.
    """
    folder_entity = get_current_folder_entity(fields={"attrib"})

    fps = float(folder_entity["attrib"].get("fps", 25))
    rv.commands.setFPS(fps)
