"""Telemetry analytics: accumulate per-tick Lotka-Volterra metrics into a Polars DataFrame.

The :class:`TelemetryRecorder` accumulates per-tick population and energy metrics into an
in-memory row buffer and exposes a lazily-constructed :class:`polars.DataFrame` for
downstream export, Chart.js serialisation, and statistical aggregation. Each recorded tick
captures both aggregate scalars (total flora energy, total predator population) and
granular per-species dictionaries (population and aggregate energy keyed by
``species_id``), thereby enabling precise Lotka-Volterra phase-space visualisation and
Monte Carlo batch evaluation.

The per-species data is accumulated via ``defaultdict`` accumulators inside
:meth:`TelemetryRecorder.record` so that sparse or absent species naturally resolve to
zero without requiring sentinel guards. Active defense-maintenance costs are also
attributed per flora ``species_id`` by querying
:class:`~phids.engine.components.substances.SubstanceComponent` entities whose ``active``
flag is set, summing their ``energy_cost_per_tick`` contribution. This diagnostic
facilitates identification of runaway defense-maintenance scenarios in which an entire
connected mycorrhizal network commits metabolic resources to sustained chemical defense
under persistent herbivore pressure.

The :attr:`TelemetryRecorder.dataframe` property materialises a fully rectangular Polars
DataFrame that preserves per-species breakdowns as typed scalar columns
(``plant_{id}_pop``, ``plant_{id}_energy``, ``defense_cost_{id}``,
``swarm_{id}_pop``). This columnar representation exposes the per-species data through
the primary CSV and NDJSON export routes without requiring callers to reach into the raw
``_rows`` buffer or invoke the auxiliary
:func:`~phids.telemetry.export.telemetry_to_dataframe` pandas-conversion helper. Species
identifiers observed across the accumulated session are unioned and sorted before columns
are written, guaranteeing a consistent column order even when individual ticks contain
sparse species sets.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

import polars as pl

from phids.engine.components.plant import PlantComponent
from phids.engine.components.substances import SubstanceComponent
from phids.engine.components.swarm import SwarmComponent
from phids.engine.core.ecs import ECSWorld
from phids.shared.constants import MAX_TELEMETRY_TICKS

logger = logging.getLogger(__name__)


class TelemetryRecorder:
    """Accumulate per-tick Lotka-Volterra metrics into a Polars DataFrame.

    The recorder appends one row per tick and materialises a lazily-built Polars
    DataFrame containing aggregate scalars together with per-species flat columns.
    Aggregate fields comprise ``tick``, ``total_flora_energy``, ``flora_population``,
    ``predator_clusters``, ``predator_population``, and the five per-tick plant death
    cause counts (``death_reproduction``, ``death_mycorrhiza``,
    ``death_defense_maintenance``, ``death_herbivore_feeding``,
    ``death_background_deficit``). Per-species breakdowns are exposed as typed Polars
    scalar columns following the naming convention ``plant_{id}_pop``,
    ``plant_{id}_energy``, ``swarm_{id}_pop``, and ``defense_cost_{id}``, where
    ``{id}`` denotes the integer ``species_id``. Missing species in a given tick are
    zero-filled to guarantee a fully rectangular DataFrame suitable for vectorised
    statistical operations and direct CSV or NDJSON export.
    """

    def __init__(self, max_rows: int = MAX_TELEMETRY_TICKS) -> None:
        """Create a TelemetryRecorder with empty in-memory buffers.

        Args:
            max_rows: Maximum in-memory tick rows retained in the rolling window.
        """
        self._rows: list[dict[str, Any]] = []
        self._df: pl.DataFrame | None = None
        self._max_rows = max(1, int(max_rows))

    def record(
        self,
        world: ECSWorld,
        tick: int,
        plant_death_causes: dict[str, int] | None = None,
    ) -> None:
        """Snapshot current ECS metrics and append to the internal buffer.

        Iterates over all :class:`~phids.engine.components.plant.PlantComponent`,
        :class:`~phids.engine.components.swarm.SwarmComponent`, and active
        :class:`~phids.engine.components.substances.SubstanceComponent` entities
        to build aggregate and per-species counters. All per-species keys are
        written unconditionally (with zero defaults) so that downstream pandas
        and Polars operations encounter a fully rectangular schema without null
        values.

        Args:
            world: The ECS world to sample entity components from.
            tick: Current simulation tick index.
            plant_death_causes: Per-tick plant death diagnostics keyed by cause.
        """
        total_flora_energy = 0.0
        flora_population = 0
        plant_pop_by_species: dict[int, int] = defaultdict(int)
        plant_energy_by_species: dict[int, float] = defaultdict(float)

        for entity in world.query(PlantComponent):
            plant: PlantComponent = entity.get_component(PlantComponent)
            total_flora_energy += plant.energy
            flora_population += 1
            plant_pop_by_species[plant.species_id] += 1
            plant_energy_by_species[plant.species_id] += plant.energy

        predator_clusters = 0
        predator_population = 0
        swarm_pop_by_species: dict[int, int] = defaultdict(int)

        for entity in world.query(SwarmComponent):
            swarm: SwarmComponent = entity.get_component(SwarmComponent)
            predator_clusters += 1
            predator_population += swarm.population
            swarm_pop_by_species[swarm.species_id] += swarm.population

        defense_cost_by_species: dict[int, float] = defaultdict(float)
        for entity in world.query(SubstanceComponent):
            sub: SubstanceComponent = entity.get_component(SubstanceComponent)
            if not sub.active or sub.energy_cost_per_tick <= 0.0:
                continue
            owner = (
                world.get_entity(sub.owner_plant_id)
                if world.has_entity(sub.owner_plant_id)
                else None
            )
            if owner is None:
                continue
            if owner.has_component(PlantComponent):
                plant_owner: PlantComponent = owner.get_component(PlantComponent)
                defense_cost_by_species[plant_owner.species_id] += sub.energy_cost_per_tick

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

        row: dict[str, Any] = {
            "tick": tick,
            "total_flora_energy": total_flora_energy,
            "flora_population": flora_population,
            "predator_clusters": predator_clusters,
            "predator_population": predator_population,
            **death_counts,
            # Per-species flat columns
            "plant_pop_by_species": dict(plant_pop_by_species),
            "plant_energy_by_species": dict(plant_energy_by_species),
            "swarm_pop_by_species": dict(swarm_pop_by_species),
            "defense_cost_by_species": dict(defense_cost_by_species),
        }
        self._rows.append(row)
        if len(self._rows) > self._max_rows:
            # Enforce bounded telemetry memory by dropping oldest ticks first.
            overflow = len(self._rows) - self._max_rows
            del self._rows[:overflow]
        self._df = None  # invalidate cache
        logger.debug(
            "Telemetry row recorded (tick=%d, flora=%d, predators=%d, flora_energy=%.2f)",
            tick,
            flora_population,
            predator_population,
            total_flora_energy,
        )

    def get_latest_metrics(self) -> dict[str, Any] | None:
        """Return the latest recorded telemetry row, if available.

        Returns:
            dict[str, Any] | None: Most recent metrics row or ``None``.
        """
        if not self._rows:
            return None
        return self._rows[-1]

    def get_species_ids(self) -> dict[str, list[int]]:
        """Return the union of all flora and predator species ids seen so far.

        Scans all accumulated rows to collect every species id that has
        appeared at least once in the simulation history, enabling Chart.js
        dataset generation to create series for species that may have gone
        extinct mid-simulation.

        Returns:
            dict[str, list[int]]: Keys ``"flora_ids"`` and ``"predator_ids"``
            each mapping to a sorted list of integer species identifiers.
        """
        flora_ids: set[int] = set()
        predator_ids: set[int] = set()
        for row in self._rows:
            flora_ids.update(row.get("plant_pop_by_species", {}).keys())
            predator_ids.update(row.get("swarm_pop_by_species", {}).keys())
        return {
            "flora_ids": sorted(flora_ids),
            "predator_ids": sorted(predator_ids),
        }

    @property
    def dataframe(self) -> pl.DataFrame:
        """Return recorded metrics as a Polars DataFrame with per-species flat columns (lazily built).

        Per-species dictionary accumulators stored in each row's
        ``plant_pop_by_species``, ``plant_energy_by_species``,
        ``swarm_pop_by_species``, and ``defense_cost_by_species`` fields are
        flattened into typed Polars scalar columns named ``plant_{id}_pop``
        (``Int64``), ``plant_{id}_energy`` (``Float64``), ``swarm_{id}_pop``
        (``Int64``), and ``defense_cost_{id}`` (``Float64``) respectively.
        Missing species values for a given tick are zero-filled, ensuring the
        resulting DataFrame is fully rectangular and free of null entries.

        All species identifiers observed across the full retention window are
        unioned and sorted prior to column construction, so that the column
        layout is deterministic and consistent even when individual ticks contain
        sparse species sets due to extinction or delayed colonisation events.

        The empty-state DataFrame (no recorded ticks) retains only the stable
        aggregate schema; per-species columns are added dynamically once at
        least one tick has been recorded and at least one species has been
        observed, reflecting the inherently dynamic cardinality of the species
        pool across independent simulation sessions.

        Returns:
            pl.DataFrame: DataFrame containing aggregate and per-species flat
            telemetry columns for all accumulated ticks.
        """
        if self._df is None:
            logger.debug("Materialising telemetry dataframe from %d rows", len(self._rows))
            if self._rows:
                # Union of all species IDs observed across the full retention window
                all_flora_ids: set[int] = set()
                all_swarm_ids: set[int] = set()
                for r in self._rows:
                    all_flora_ids.update(r.get("plant_pop_by_species", {}).keys())
                    all_swarm_ids.update(r.get("swarm_pop_by_species", {}).keys())
                sorted_flora = sorted(all_flora_ids)
                sorted_swarm = sorted(all_swarm_ids)

                # Build flat rows: aggregate scalars + per-species flat columns
                flat_rows: list[dict[str, Any]] = []
                for r in self._rows:
                    flat: dict[str, Any] = {k: v for k, v in r.items() if not isinstance(v, dict)}
                    for fid in sorted_flora:
                        flat[f"plant_{fid}_pop"] = int(
                            r.get("plant_pop_by_species", {}).get(fid, 0)
                        )
                        flat[f"plant_{fid}_energy"] = float(
                            r.get("plant_energy_by_species", {}).get(fid, 0.0)
                        )
                        flat[f"defense_cost_{fid}"] = float(
                            r.get("defense_cost_by_species", {}).get(fid, 0.0)
                        )
                    for sid in sorted_swarm:
                        flat[f"swarm_{sid}_pop"] = int(
                            r.get("swarm_pop_by_species", {}).get(sid, 0)
                        )
                    flat_rows.append(flat)
                self._df = pl.DataFrame(flat_rows)
            else:
                # Stable aggregate-only schema when no ticks have been recorded.
                # Per-species columns are absent because no species IDs are yet known;
                # they will be added dynamically on the first post-tick materialisation.
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
