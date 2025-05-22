"""Type hints for rv.extra_commands module."""

from typing import Dict, List


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
