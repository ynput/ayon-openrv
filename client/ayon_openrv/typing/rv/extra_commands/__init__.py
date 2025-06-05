"""Type hints for rv.extra_commands module."""

from typing import Dict, List, Any, Optional


def findAnnotatedFrames() -> List[int]:
    """
    Return a list of frame numbers that have annotations.

    Returns:
        List[int]: A list of frame numbers with annotations.
        The array is not sorted and some frames may appear more than once.
    """
    ...


def nodesInGroupOfType(groupNode: str, nodeType: str) -> List[str]:
    """
    Find all nodes of a specific type within a group.

    Args:
        groupNode (str): The group node to search in.
        nodeType (str): The type of node to search for.

    Returns:
        List[str]: A list of node names of the specified type.
    """
    ...


def markFrameStart() -> int:
    """
    Get the start frame of the current mark range.

    Returns:
        int: The start frame of the mark range.
    """
    ...


def markFrameEnd() -> int:
    """
    Get the end frame of the current mark range.

    Returns:
        int: The end frame of the mark range.
    """
    ...


def isFrameMarked(frame: int) -> bool:
    """
    Check if a specific frame is marked.

    Args:
        frame (int): The frame number to check.

    Returns:
        bool: True if the frame is marked, False otherwise.
    """
    ...


def getAnnotationText(frame: int) -> str:
    """
    Get the annotation text for a specific frame.

    Args:
        frame (int): The frame number.

    Returns:
        str: The annotation text for the frame.
    """
    ...


def setAnnotationText(frame: int, text: str) -> None:
    """
    Set the annotation text for a specific frame.

    Args:
        frame (int): The frame number.
        text (str): The text to set as annotation.
    """
    ...


def deleteAnnotation(frame: int) -> None:
    """
    Delete the annotation for a specific frame.

    Args:
        frame (int): The frame number.
    """
    ...


def getAnnotations() -> Dict[int, str]:
    """
    Get all annotations in the current session.

    Returns:
        Dict[int, str]: A dictionary mapping frame numbers to annotation text.
    """
    ...


def getAllNodesOfType(nodeType: str) -> List[str]:
    """
    Find all nodes of a specific type in the entire session.

    Args:
        nodeType (str): The type of node to search for.

    Returns:
        List[str]: A list of node names of the specified type.
    """
    ...


def getGroupNodesOfType(groupNode: str, nodeType: str, recursive: bool = False) -> List[str]:
    """
    Find nodes of a specific type within a group, optionally recursively.

    Args:
        groupNode (str): The group node to search in.
        nodeType (str): The type of node to search for.
        recursive (bool, optional): Whether to search recursively in subgroups.

    Returns:
        List[str]: A list of node names of the specified type.
    """
    ...

# Missing commands from all_extra_commands in OpenRV source
def popInputToTop() -> None:
    """
    Pops the current input node to the top of the node graph.
    """
    ...

def stepBackward10() -> None:
    """
    Steps backward by 10 frames.
    """
    ...

def reloadInOut() -> None:
    """
    Reloads media within the in and out points.
    """
    ...

def loadCurrentSourcesChangedFrames() -> None:
    """
    Loads changed frames for current sources.
    """
    ...

def nodesInEvalPath(nodeName: str) -> List[str]:
    """
    Finds nodes in the evaluation path of a given node.
    """
    ...

def setUIName(nodeName: str, uiName: str) -> None:
    """
    Sets the UI name for a node.
    """
    ...

def displayFeedback2(message: str, duration: float = 2.0) -> None:
    """
    Displays feedback message in the UI.
    """
    ...

def inputNodeUserNameAtFrame(nodeName: str, frame: int, userName: str) -> str:
    """
    Gets the input node user name at a specific frame.
    """
    ...

def sourceMetaInfoAtFrame(sourceNode: str, frame: int) -> Dict[str, Any]:
    """
    Gets meta information for a source at a specific frame.
    """
    ...

def sourceImageStructure(sourceNode: str) -> Dict[str, Any]:
    """
    Gets the image structure for a source node.
    """
    ...

def stepBackward100() -> None:
    """
    Steps backward by 100 frames.
    """
    ...

def setTranslation(x: float, y: float) -> None:
    """
    Sets the translation of the current view.
    """
    ...

def stepForward100() -> None:
    """
    Steps forward by 100 frames.
    """
    ...

def isPlayingForwards() -> bool:
    """
    Checks if playback is currently moving forwards.
    """
    ...

def setInactiveState() -> None:
    """
    Sets RV to an inactive state.
    """
    ...

def stepBackward() -> None:
    """
    Steps backward by one frame.
    """
    ...

def activatePackageModeEntry(packageName: str, modeName: str) -> None:
    """
    Activates a specific mode entry within a package.
    """
    ...

def isViewNode(nodeName: str) -> bool:
    """
    Checks if a node is the current view node.
    """
    ...

def toggleFilter(filterName: str) -> None:
    """
    Toggles a specific filter.
    """
    ...

def topLevelGroup() -> str:
    """
    Gets the top-level group node.
    """
    ...

def deactivatePackageModeEntry(packageName: str, modeName: str) -> None:
    """
    Deactivates a specific mode entry within a package.
    """
    ...

def set(variableName: str, value: Any) -> None:
    """
    Sets the value of a variable.
    """
    ...

def associatedNode(nodeName: str, associationType: str) -> Optional[str]:
    """
    Gets an associated node of a specific type.
    """
    ...

def cycleNodeInputs(nodeName: str) -> None:
    """
    Cycles through the inputs of a node.
    """
    ...

def toggleFullScreen() -> None:
    """
    Toggles full screen mode.
    """
    ...

def currentImageAspect() -> float:
    """
    Gets the aspect ratio of the current image.
    """
    ...

def frameImage() -> None:
    """
    Frames the current image in the view.
    """
    ...

def activateSync(connectionName: str) -> None:
    """
    Activates synchronization with a remote connection.
    """
    ...

def cacheUsage() -> Dict[str, Any]:
    """
    Gets information about cache usage.
    """
    ...

def toggleRealtime() -> None:
    """
    Toggles realtime playback mode.
    """
    ...

def toggleMotionScope() -> None:
    """
    Toggles the motion scope overlay.
    """
    ...

def isNarrowed() -> bool:
    """
    Checks if the view is narrowed to a range.
    """
    ...

def isPlayable() -> bool:
    """
    Checks if the current session is playable.
    """
    ...

def isPlayingBackwards() -> bool:
    """
    Checks if playback is currently moving backwards.
    """
    ...

def scale() -> float:
    """
    Gets the current view scale.
    """
    ...

def toggleMotionScopeFromState(state: bool) -> None:
    """
    Toggles motion scope based on a boolean state.
    """
    ...

def setScale(scale: float) -> None:
    """
    Sets the current view scale.
    """
    ...

def recordPixelInfo(enable: bool) -> None:
    """
    Enables or disables recording of pixel information.
    """
    ...

def setActiveState() -> None:
    """
    Sets RV to an active state.
    """
    ...

def displayFeedback(message: str) -> None:
    """
    Displays feedback message (older version, displayFeedback2 preferred).
    """
    ...

def togglePlay() -> None:
    """
    Toggles playback (play/pause).
    """
    ...

def sequenceBoundaries() -> List[int]:
    """
    Gets the start and end frames of the current sequence.
    """
    ...

def togglePlayIfNoScrub() -> None:
    """
    Toggles playback only if not currently scrubbing.
    """
    ...

def isSessionEmpty() -> bool:
    """
    Checks if the current session is empty.
    """
    ...

def togglePlayVerbose() -> None:
    """
    Toggles playback with verbose output.
    """
    ...

def associatedNodes(nodeName: str, associationType: str) -> List[str]:
    """
    Gets all associated nodes of a specific type.
    """
    ...

def toggleForwardsBackwards() -> None:
    """
    Toggles playback direction.
    """
    ...

def translation() -> List[float]:
    """
    Gets the current view translation [x, y].
    """
    ...

def stepForward1() -> None:
    """
    Steps forward by one frame.
    """
    ...

def stepForward10() -> None:
    """
    Steps forward by 10 frames.
    """
    ...

def sourceFrame(sourceNode: str) -> int:
    """
    Gets the current frame of a specific source node.
    """
    ...

def nodesUnderPointer(x: int, y: int) -> List[str]:
    """
    Gets the names of nodes under the mouse pointer coordinates.
    """
    ...

def centerResizeFit() -> None:
    """
    Centers the view and resizes to fit the current image.
    """
    ...

def numFrames() -> int:
    """
    Gets the total number of frames in the session.
    """
    ...

def toggleSync(connectionName: str) -> None:
    """
    Toggles synchronization with a remote connection.
    """
    ...

def stepBackward1() -> None:
    """
    Steps backward by one frame (duplicate definition).
    """
    ...

def uiName(nodeName: str) -> str:
    """
    Gets the UI name of a node.
    """
    ...

def stepForward() -> None:
    """
    Steps forward by one frame.
    """
    ...

def cprop(nodeName: str, propName: str) -> str:
    """
    Gets a property value as a string (convenience function).
    """
    ...

def appendToProp(nodeName: str, propName: str, value: Any) -> None:
    """
    Appends a value to a node property.
    """
    ...

def removeFromProp(nodeName: str, propName: str, value: Any) -> None:
    """
    Removes a value from a node property.
    """
    ...

def existsInProp(nodeName: str, propName: str, value: Any) -> bool:
    """
    Checks if a value exists in a node property.
    """
    ...

def associatedVideoDevice(sourceNode: str) -> str:
    """
    Gets the associated video device for a source node.
    """
    ...

def updatePixelInfo() -> None:
    """
    Updates the displayed pixel information.
    """
    ...

def setDisplayProfilesFromSettings(enable: bool) -> None:
    """
    Sets display profiles based on settings.
    """
    ...

def minorModeIsLoaded(modeName: str) -> bool:
    """
    Checks if a minor mode is loaded.
    """
    ...
