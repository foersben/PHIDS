"""Telemetry analytics: Polars DataFrame accumulation of Lotka-Volterra metrics."""

from __future__ import annotations

from typing import Any

import polars as pl

from phytodynamics.engine.components.plant import PlantComponent
from phytodynamics.engine.components.swarm import SwarmComponent
from phytodynamics.engine.core.ecs import ECSWorld


class TelemetryRecorder:
    """Accumulates per-tick Lotka-Volterra metrics into a Polars DataFrame.

    Metrics recorded per tick
    -------------------------
    * tick               – simulation tick index.
    * total_flora_energy – sum of energy across all plant entities.
    * flora_population   – total count of living plant entities.
    * predator_clusters  – total number of active swarm entities.
    * predator_population – total head-count across all swarm entities.
    """

    def __init__(self) -> None:
        self._rows: list[dict[str, Any]] = []
        self._df: pl.DataFrame | None = None

    def record(self, world: ECSWorld, tick: int) -> None:
        """Snapshot current metrics and append to internal buffer."""
        total_flora_energy = 0.0
        flora_population = 0
        for entity in world.query(PlantComponent):
            plant: PlantComponent = entity.get_component(PlantComponent)
            total_flora_energy += plant.energy
            flora_population += 1

        predator_clusters = 0
        predator_population = 0
        for entity in world.query(SwarmComponent):
            swarm: SwarmComponent = entity.get_component(SwarmComponent)
            predator_clusters += 1
            predator_population += swarm.population

        self._rows.append(
            {
                "tick": tick,
                "total_flora_energy": total_flora_energy,
                "flora_population": flora_population,
                "predator_clusters": predator_clusters,
                "predator_population": predator_population,
            }
        )
        self._df = None  # invalidate cache

    @property
    def dataframe(self) -> pl.DataFrame:
        """Return all recorded metrics as a Polars DataFrame (lazily built)."""
        if self._df is None:
            if self._rows:
                self._df = pl.DataFrame(self._rows)
            else:
                self._df = pl.DataFrame(
                    {
                        "tick": pl.Series([], dtype=pl.Int64),
                        "total_flora_energy": pl.Series([], dtype=pl.Float64),
                        "flora_population": pl.Series([], dtype=pl.Int64),
                        "predator_clusters": pl.Series([], dtype=pl.Int64),
                        "predator_population": pl.Series([], dtype=pl.Int64),
                    }
                )
        return self._df

    def reset(self) -> None:
        """Clear accumulated telemetry."""
        self._rows = []
        self._df = None
