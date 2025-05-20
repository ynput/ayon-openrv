"""review code"""
import os

import rv


def get_path_annotated_frame(frame=None, folder_name=None, folder_path=None):
    """Get path for annotations
    """
    # TODO: This should be less hardcoded
    filename = os.path.normpath(
        "{}/ayon/exports/annotated_frames/annotate_{}_{}.jpg".format(
            str(folder_path),
            str(folder_name),
            str(frame)
        )
    )
    return filename


def extract_annotated_frame(filepath=None):
    """Export frame to file
    """
    if filepath:
        return rv.commands.exportCurrentFrame(filepath)


def review_attributes(node=None):
    # TODO: Implement
    # prop_status = node + ".ayon" + ".review_status"
    # prop_comment = node + ".ayon" + ".review_comment"
    pass


def get_review_attribute(node=None, attribute=None):
    # backward compatibility
    attr = node + ".ayon" + "." + attribute
    attr_value = rv.commands.getStringProperty(attr)[0]

    # TODO: remove this later
    if attr_value == "":
        attr = node + ".openpype" + "." + attribute
        attr_value = rv.commands.getStringProperty(attr)[0]

    return attr_value


def write_review_attribute(node=None, attribute=None, att_value=None):
    att_prop = node + ".ayon" + ".{}".format(attribute)
    if not rv.commands.propertyExists(att_prop):
        rv.commands.newProperty(att_prop, rv.commands.StringType, 1)
    rv.commands.setStringProperty(att_prop, [str(att_value)], True)


def export_current_view_frame(frame=None, export_path=None):
    rv.commands.setFrame(int(frame))
    rv.commands.exportCurrentFrame(export_path)
