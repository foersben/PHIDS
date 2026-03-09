from __future__ import annotations

from phytodynamics.api.main import app


def test_required_routes_present() -> None:
    paths = {route.path for route in app.router.routes}

    assert "/api/scenario/load" in paths
    assert "/api/simulation/start" in paths
    assert "/api/simulation/pause" in paths
    assert "/ws/simulation/stream" in paths
