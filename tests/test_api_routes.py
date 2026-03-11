from __future__ import annotations

from phids.api.main import app


def test_required_routes_present() -> None:
    paths = {route.path for route in app.router.routes}

    assert "/api/scenario/load" in paths
    assert "/api/simulation/start" in paths
    assert "/api/simulation/pause" in paths
    assert "/api/simulation/step" in paths
    assert "/api/simulation/reset" in paths
    assert "/api/ui/cell-details" in paths
    assert "/ws/simulation/stream" in paths
    assert "/ws/ui/stream" in paths
