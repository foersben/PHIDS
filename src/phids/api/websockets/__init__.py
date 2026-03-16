"""WebSocket transport managers for PHIDS API streaming surfaces.

This package encapsulates connection-oriented orchestration for the binary simulation stream and
the JSON UI stream. Separating these loops from the FastAPI composition root keeps runtime state
ownership in ``phids.api.main`` while moving transport cadence, payload emission, and disconnect
handling into reusable manager classes.
"""

from phids.api.websockets.manager import SimulationStreamManager, UIStreamManager

__all__ = ["SimulationStreamManager", "UIStreamManager"]
