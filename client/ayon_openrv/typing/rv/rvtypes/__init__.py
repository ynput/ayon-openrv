"""Type hints for rv.rvtypes module."""

from typing import Any, Callable, List, Optional, Tuple


class MinorMode:
    """Base class for defining minor modes in RV.

    Minor modes are used to extend the UI of RV with custom menus, keybindings,
    and event handlers.
    """

    def __init__(self) -> None:
        """Initialize a new minor mode."""
        pass

    def init(self,
             name: str,
             globalBindings: Optional[List] = None,
             overrideBindings: Optional[List[Tuple[str, Callable, str]]] = None,
             menu: Optional[List[Tuple[str, List]]] = None,
             sortKey: Optional[str] = None,
             ordering: Optional[int] = None) -> None:
        """Initialize the minor mode with the given parameters.

        Args:
            name: Unique identifier for this mode
            globalBindings: Global key bindings
            overrideBindings: Event overrides in the form (event_name, callback, description)
            menu: Menu structure to create or augment
            sortKey: Sort key for ordering modes
            ordering: Numeric ordering value
        """
        pass


class Event:
    """Base class for RV events."""

    def name(self) -> str:
        """Get the name of the event.

        Returns:
            str: The event name
        """
        pass

    def contents(self) -> str:
        """Get the contents/payload of the event.

        Returns:
            str: The event contents
        """
        pass


class PixelBlockTransferEvent(Event):
    """Event for transferring pixel blocks."""

    def media(self) -> str:
        """Get the media name."""
        ...

    def view(self) -> str:
        """Get the view name."""
        ...

    def layer(self) -> str:
        """Get the layer name."""
        ...

    def frame(self) -> int:
        """Get the frame number."""
        ...

    def x(self) -> int:
        """Get the x coordinate."""
        ...

    def y(self) -> int:
        """Get the y coordinate."""
        ...

    def width(self) -> int:
        """Get the width."""
        ...

    def height(self) -> int:
        """Get the height."""
        ...

    def pixels(self) -> Any:
        """Get the pixel data."""
        ...

    def size(self) -> int:
        """Get the size of the pixel data."""
        ...


def createMode() -> MinorMode:
    """Function that RV calls to create a mode.

    This function must be implemented by each package.

    Returns:
        MinorMode: The created mode
    """
    ...
