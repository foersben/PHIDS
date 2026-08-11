"""Cell details dashboard presenters."""

from .live import build_live_cell_details
from .preview import build_preview_cell_details

__all__ = [
    "build_live_cell_details",
    "build_preview_cell_details",
]
