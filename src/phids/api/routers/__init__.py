"""Router partition for the PHIDS HTTP surface.

This package separates low-risk route families from the application composition root so that the
server can evolve toward a modular FastAPI topology without disturbing the deterministic
simulation runtime that remains anchored in `phids.api.main`. The extracted routers presently
cover operator-facing HTML surfaces and telemetry transport surfaces. They preserve the canonical
server-side Jinja workflow, the draft-versus-live state boundary, and the analytical export
semantics required for ecological observation and post hoc inference.
"""

from .batch import router as batch_router
from .config import router as config_router
from .simulation import router as simulation_router
from .telemetry import router as telemetry_router
from .ui import router as ui_router

__all__ = [
    "batch_router",
    "config_router",
    "simulation_router",
    "telemetry_router",
    "ui_router",
]
