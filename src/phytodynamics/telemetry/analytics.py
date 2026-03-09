"""Telemetry analytics: accumulate Lotka-Volterra metrics into a DataFrame.

The :class:`TelemetryRecorder` accumulates per-tick metrics into an in-memory
buffer and exposes a lazily-built :class:`polars.DataFrame` for export.
"""
from __future__ import annotations

from typing import Any

import polars as pl

from phytodynamics.engine.components.plant import PlantComponent
from phytodynamics.engine.components.swarm import SwarmComponent
from phytodynamics.engine.core.ecs import ECSWorld


class TelemetryRecorder:
    """Accumulate per-tick Lotka-Volterra metrics into a Polars DataFrame.

    The recorder stores rows containing the following fields per tick:
    ``tick``, ``total_flora_energy``, ``flora_population``,
    ``predator_clusters``, ``predator_population``.
    """

    def __init__(self) -> None:
        """Create a TelemetryRecorder with empty in-memory buffers."""
        self._rows: list[dict[str, Any]] = []
        self._df: pl.DataFrame | None = None

    def record(self, world: ECSWorld, tick: int) -> None:
        """Snapshot current metrics and append to the internal buffer.

        Args:
            world: The ECS world to sample entity components from.
            tick: Current simulation tick index.
        """
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
        """Return recorded metrics as a Polars DataFrame (lazily built).

        Returns:
            pl.DataFrame: DataFrame containing accumulated telemetry rows.
        """
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
        """Clear accumulated telemetry and reset internal cache."""
        self._rows = []
        self._df = None
