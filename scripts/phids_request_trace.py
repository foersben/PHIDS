from __future__ import annotations

import asyncio

from httpx import ASGITransport, AsyncClient

from phids.api.main import app
from phids.shared.logging_config import configure_logging

PAYLOAD = {
    "grid_width": 8,
    "grid_height": 8,
    "max_ticks": 5,
    "tick_rate_hz": 10.0,
    "num_signals": 2,
    "num_toxins": 2,
    "wind_x": 0.0,
    "wind_y": 0.0,
    "flora_species": [
        {
            "species_id": 0,
            "name": "Grass",
            "base_energy": 10.0,
            "max_energy": 20.0,
            "growth_rate": 5.0,
            "survival_threshold": 1.0,
            "reproduction_interval": 2,
            "seed_min_dist": 1.0,
            "seed_max_dist": 2.0,
            "seed_energy_cost": 2.0,
            "triggers": [],
        }
    ],
    "predator_species": [
        {
            "species_id": 0,
            "name": "Herbivore",
            "energy_min": 1.0,
            "velocity": 1,
            "consumption_rate": 1.0,
            "reproduction_energy_divisor": 1.0,
        }
    ],
    "diet_matrix": {"rows": [[True]]},
    "initial_plants": [{"species_id": 0, "x": 2, "y": 2, "energy": 10.0}],
    "initial_swarms": [{"species_id": 0, "x": 2, "y": 2, "population": 3, "energy": 3.0}],
    "mycorrhizal_inter_species": False,
    "mycorrhizal_connection_cost": 1.0,
    "mycorrhizal_signal_velocity": 1,
}


async def main() -> None:
    configure_logging(force=True)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.get("/")
        await client.get("/api/simulation/status")
        await client.post("/api/scenario/load", json=PAYLOAD)
        await client.post("/api/simulation/start", headers={"HX-Request": "true"})
        await client.get("/api/simulation/status")
        await client.get("/api/telemetry")


if __name__ == "__main__":
    asyncio.run(main())
