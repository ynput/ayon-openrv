"""Type hints for rv.qtutils module."""

from typing import Any, Optional
from qtpy import QtWidgets


def sessionWindow() -> QtWidgets.QMainWindow:
    """
    Returns the main window for the current RV session.
    
    Returns:
        QtWidgets.QMainWindow: The main RV application window.
    """
    ...

def getLayer() -> Any:
    """
    Returns the current layer.
    
    Returns:
        Any: The current layer object.
    """
    ...

def getView() -> Any:
    """
    Returns the current view.
    
    Returns:
        Any: The current view object.
    """
    ...

def dockWidget(widget: QtWidgets.QWidget, 
               title: str, 
               area: Optional[int] = None, 
               parent: Optional[QtWidgets.QMainWindow] = None) -> QtWidgets.QDockWidget:
    """
    Dock a widget in the RV interface.
    
    Args:
        widget (QtWidgets.QWidget): The widget to dock
        title (str): Title of the dock widget
        area (Optional[int]): Dock area to use (Qt.DockWidgetArea)
        parent (Optional[QtWidgets.QMainWindow]): Parent window, defaults to sessionWindow()
        
    Returns:
        QtWidgets.QDockWidget: The created dock widget
    """
    ...