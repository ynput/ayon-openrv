"""Type hints for RV API."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from . import rv

__all__ = ["rv"]