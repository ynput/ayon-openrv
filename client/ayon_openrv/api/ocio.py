"""Helper functions to apply OCIO colorspace settings on source groups.

This drives the mode of the OpenColorIO Basic Color Management package
(`ocio_source_setup`) that ships with OpenRV, so RV's OCIO menu stays in sync
with what we set. The package is optional in OpenRV and only loaded when the
user enabled it in the preferences, so we load its mode on demand if needed.

"""
from __future__ import annotations

import gc
import logging
import os
import sys

import rv.commands

from .lib import group_member_of_type

log = logging.getLogger(__name__)

OCIO_MODE_NAME = "OCIO Source Setup"
OCIO_MODULE_NAME = "ocio_source_setup"

# The OCIO mode instance we are driving, cached after the first lookup
_ocio_mode = None


class OCIONotActiveForGroup(RuntimeError):
    """Error raised when OCIO is not enabled on the group node."""


class OCIOUnavailableError(RuntimeError):
    """Error raised when OCIO can't be used in the current OpenRV session."""


def get_group_ocio_look_node(group):
    """Return OCIOLook node from source group"""
    # make sure this only runs if OCIO is set
    if os.environ.get("OCIO") is None:
        return

    pipeline = group_member_of_type(group, "RVLookPipelineGroup")
    if pipeline:
        return group_member_of_type(pipeline, "OCIOLook")


def get_group_ocio_file_node(group):
    """Return OCIOFile node from source group"""
    # make sure this only runs if OCIO is set
    if os.environ.get("OCIO") is None:
        return

    pipeline = group_member_of_type(group, "RVLinearizePipelineGroup")
    if pipeline:
        return group_member_of_type(pipeline, "OCIOFile")


def get_ocio_mode():
    """Return the active mode of the OpenRV OCIO package.

    When OpenRV did not load the optional package on startup, the mode is
    created and activated here. That also adds RV's OCIO menu.

    Raises:
        OCIOUnavailableError: When the OCIO package is not available.

    Returns:
        ocio_source_setup.OCIOSourceSetupMode: The active OCIO mode.

    """
    global _ocio_mode
    if _ocio_mode is not None and rv.commands.isModeActive(OCIO_MODE_NAME):
        return _ocio_mode

    already_imported = OCIO_MODULE_NAME in sys.modules
    try:
        import ocio_source_setup
    except ImportError as exc:
        raise OCIOUnavailableError(
            f"The OpenRV OCIO package ({OCIO_MODULE_NAME}) is not available."
        ) from exc

    mode = _ocio_mode
    if mode is None and already_imported:
        # OpenRV's mode manager may have loaded the mode on startup. It does
        # not expose the instance, so find it instead.
        mode = next(
            (
                obj for obj in gc.get_objects()
                if isinstance(obj, ocio_source_setup.OCIOSourceSetupMode)
            ),
            None,
        )

    if mode is None:
        if rv.commands.isModeActive(OCIO_MODE_NAME):
            raise OCIOUnavailableError(
                f"The '{OCIO_MODE_NAME}' mode is active, but its instance"
                " could not be found."
            )
        log.info("Loading the OpenRV OCIO package on demand.")
        mode = ocio_source_setup.createMode()

    if not rv.commands.isModeActive(OCIO_MODE_NAME):
        # Make sure `toggle()` activates the mode
        mode._active = False
        mode.toggle()

    _ocio_mode = mode
    return mode


def get_ocio_config(mode=None):
    """Return the OCIO config used by OpenRV.

    Args:
        mode (Optional[ocio_source_setup.OCIOSourceSetupMode]): The OCIO
            mode, its config is preferred when set.

    Raises:
        OCIOUnavailableError: When the OCIO config can't be read.

    Returns:
        PyOpenColorIO.Config: The OCIO config.

    """
    config = getattr(mode, "config", None)
    if config is not None:
        return config

    import PyOpenColorIO as OCIO
    try:
        return OCIO.GetCurrentConfig()
    except Exception as exc:
        raise OCIOUnavailableError(
            f"Unable to read the OCIO config '{os.environ.get('OCIO')}':"
            f" {exc}"
        ) from exc


def set_group_ocio_colorspace(group, colorspace):
    """Enable OCIO for the source group and set its file colorspace.

    When this is the first source using OCIO, the displays are switched to
    OCIO as well. That matches what the OCIO package does for new sources.

    Args:
        group (str): The source group node.
        colorspace (str): The colorspace of the source's media.

    Raises:
        OCIOUnavailableError: When OCIO can't be used in this session.
        ValueError: When the colorspace is not in the OCIO config.
        OCIONotActiveForGroup: When OCIO could not be enabled for the group.

    """
    # make sure this only runs if OCIO is set
    if os.environ.get("OCIO") is None:
        return

    mode = get_ocio_mode()
    config = get_ocio_config(mode)
    if config.getColorSpace(colorspace) is None:
        raise ValueError(
            f"Colorspace '{colorspace}' is not in the OCIO config"
            f" '{os.environ.get('OCIO')}'."
        )

    node = get_group_ocio_file_node(group)
    if not node:
        source = (
            group_member_of_type(group, "RVImageSource")
            or group_member_of_type(group, "RVFileSource")
        )
        mode.useSourceOCIO(source, "OCIOFile", colorspace)
        node = get_group_ocio_file_node(group)
        if not node:
            raise OCIONotActiveForGroup(
                f"Unable to enable OCIO for {group}. See the OpenRV console"
                " for details."
            )

        if len(rv.commands.nodesOfType("OCIOFile")) == 1:
            for display in rv.commands.nodesOfType("RVDisplayGroup"):
                if not mode.usingOCIOForDisplay.get(display, False):
                    mode.useDisplayOCIO(display)

    # The OCIO package prefers a colorspace parsed from the file name, so
    # always set the colorspace explicitly
    rv.commands.setStringProperty(
        f"{node}.ocio.inColorSpace", [colorspace], True
    )
