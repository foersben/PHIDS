"""DSE candidate apply endpoints.

Contains routes to apply a candidate configuration from the Design Space
Exploration (DSE) Pareto front directly back into the live system draft state.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/dse", tags=["DSE Apply"])
