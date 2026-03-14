"""Telemetry analytics: accumulate Lotka-Volterra metrics into a DataFrame.

The :class:`TelemetryRecorder` accumulates per-tick metrics into an in-memory
buffer and exposes a lazily-built :class:`polars.DataFrame` for export.
"""

from __future__ import annotations

import logging
from typing import Any

import polars as pl

from phids.engine.components.plant import PlantComponent
from phids.engine.components.swarm import SwarmComponent
from phids.engine.core.ecs import ECSWorld

logger = logging.getLogger(__name__)


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

    def record(
        self,
        world: ECSWorld,
        tick: int,
        plant_death_causes: dict[str, int] | None = None,
    ) -> None:
        """Snapshot current metrics and append to the internal buffer.

        Args:
            world: The ECS world to sample entity components from.
            tick: Current simulation tick index.
            plant_death_causes: Per-tick plant death diagnostics keyed by cause.
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

        death_counts = {
            "death_reproduction": 0,
            "death_mycorrhiza": 0,
            "death_defense_maintenance": 0,
            "death_herbivore_feeding": 0,
            "death_background_deficit": 0,
        }
        if plant_death_causes is not None:
            for key in death_counts:
                death_counts[key] = int(plant_death_causes.get(key, 0))

        self._rows.append(
            {
                "tick": tick,
                "total_flora_energy": total_flora_energy,
                "flora_population": flora_population,
                "predator_clusters": predator_clusters,
                "predator_population": predator_population,
                **death_counts,
            }
        )
        self._df = None  # invalidate cache

    def get_latest_metrics(self) -> dict[str, Any] | None:
        """Return the latest recorded telemetry row, if available.

        Returns:
            dict[str, Any] | None: Most recent metrics row or ``None``.
        """
        if not self._rows:
            return None
        return self._rows[-1]

    @property
    def dataframe(self) -> pl.DataFrame:
        """Return recorded metrics as a Polars DataFrame (lazily built).

        Returns:
            pl.DataFrame: DataFrame containing accumulated telemetry rows.
        """
        if self._df is None:
            logger.debug("Materialising telemetry dataframe from %d rows", len(self._rows))
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
                        "death_reproduction": pl.Series([], dtype=pl.Int64),
                        "death_mycorrhiza": pl.Series([], dtype=pl.Int64),
                        "death_defense_maintenance": pl.Series([], dtype=pl.Int64),
                        "death_herbivore_feeding": pl.Series([], dtype=pl.Int64),
                        "death_background_deficit": pl.Series([], dtype=pl.Int64),
                    }
                )
        return self._df

    def reset(self) -> None:
        """Clear accumulated telemetry and reset internal cache."""
        logger.info("Resetting telemetry recorder with %d buffered rows", len(self._rows))
        self._rows = []
        self._df = None
