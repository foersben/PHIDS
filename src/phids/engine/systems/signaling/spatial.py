# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Spatial lookup utilities for the signaling system."""

from __future__ import annotations

from typing import TYPE_CHECKING

from numba import njit

from phids.engine.components.plant import PlantComponent
from phids.engine.components.swarm import SwarmComponent

if TYPE_CHECKING:
    import numpy as np
    import numpy.typing as npt

    from phids.engine.core.biotope import GridEnvironment
    from phids.engine.core.ecs import ECSWorld


@njit(cache=True)
def toroidal_distance_jit(x1: int, y1: int, x2: int, y2: int, width: int, height: int) -> float:
    """Numba JIT-compiled shortest Euclidean distance calculation across a toroidal grid seam.

    Args:
        x1: X coordinate of first point.
        y1: Y coordinate of first point.
        x2: X coordinate of second point.
        y2: Y coordinate of second point.
        width: Grid width.
        height: Grid height.

    Returns:
        float: Shortest distance considering wrap-around boundary.
    """
    dx = abs(x1 - x2)
    dy = abs(y1 - y2)
    tdx = width - dx if (width - dx) < dx else dx
    tdy = height - dy if (height - dy) < dy else dy
    return float((tdx * tdx + tdy * tdy) ** 0.5)


@njit(cache=True)
def toroidal_manhattan_distance_jit(x1: int, y1: int, x2: int, y2: int, width: int, height: int) -> int:
    """Numba JIT-compiled shortest Manhattan distance calculation across a toroidal grid seam.

    Args:
        x1: X coordinate of first point.
        y1: Y coordinate of first point.
        x2: X coordinate of second point.
        y2: Y coordinate of second point.
        width: Grid width.
        height: Grid height.

    Returns:
        int: Shortest Manhattan distance considering wrap-around boundary.
    """
    dx = abs(x1 - x2)
    dy = abs(y1 - y2)
    tdx = width - dx if (width - dx) < dx else dx
    tdy = height - dy if (height - dy) < dy else dy
    return tdx + tdy


class SwarmPopulationIndex:
    """Pre-evaluated per-cell, per-species swarm population census index.

    Dense Spatial Array Indexing & Zero-Allocation Census Buffers:
    ------------------------------------------------------------------
    Signaling evaluation loops query co-located herbivore swarm populations across thousands of
    grid cells on every tick. Constructing heap-allocated Python dictionaries (`dict[tuple[int, int, int], int]`)
    and creating 3-element coordinate tuples `(x, y, species_id)` per tick introduces severe heap allocation
    churn, memory fragmentation, and garbage collection pauses.

    `SwarmPopulationIndex` encapsulates a pre-allocated 3D NumPy int32 array (`[num_species, width, height]`)
    zeroed in-place via `.fill(0)`. It exposes an O(1) dictionary-compatible `.get((x, y, species_id), 0)` method,
    bypassing Python object creation and eliminating heap allocations during hot signaling passes.
    """

    __slots__ = ("_dict", "_grid")

    def __init__(
        self,
        grid: npt.NDArray[np.int32] | None = None,
        dict_backup: dict[tuple[int, int, int], int] | None = None,
    ) -> None:
        """Initialize SwarmPopulationIndex with backing 3D array or fallback dictionary.

        Args:
            grid: Pre-allocated 3D NumPy int32 array buffer [num_species, W, H].
            dict_backup: Fallback Python dictionary mapping (x, y, species_id) -> population.
        """
        self._grid = grid
        self._dict = dict_backup

    def get(self, key: tuple[int, int, int], default: int = 0) -> int:
        """Return total swarm population at (x, y, species_id).

        Args:
            key: Tuple of (x, y, species_id).
            default: Fallback population if key is out of bounds or absent.

        Returns:
            Population integer.
        """
        if self._grid is not None:
            x, y, species_id = key
            if 0 <= species_id < self._grid.shape[0] and 0 <= x < self._grid.shape[1] and 0 <= y < self._grid.shape[2]:
                return int(self._grid[species_id, x, y])
            return default
        if self._dict is not None:
            return self._dict.get(key, default)
        return default


def _build_swarm_population_index(
    world: ECSWorld,
    env: GridEnvironment | None = None,
) -> SwarmPopulationIndex | dict[tuple[int, int, int], int]:
    """Return a per-cell, per-species swarm-population index for one signaling tick.

    Args:
        world: ECSWorld used for spatial hash lookup.
        env: Optional GridEnvironment hosting pre-allocated 3D swarm population buffer.

    Returns:
        SwarmPopulationIndex backing pre-allocated 3D array or fallback dictionary.
    """
    if env is not None:
        grid = env.reset_swarm_populations()
        num_species, width, height = grid.shape
        for entity in world.query(SwarmComponent):
            swarm: SwarmComponent = entity.get_component(SwarmComponent)
            if 0 <= swarm.species_id < num_species and 0 <= swarm.x < width and 0 <= swarm.y < height:
                grid[swarm.species_id, swarm.x, swarm.y] += swarm.population
        return SwarmPopulationIndex(grid=grid)

    populations: dict[tuple[int, int, int], int] = {}
    for entity in world.query(SwarmComponent):
        sw: SwarmComponent = entity.get_component(SwarmComponent)
        key = (sw.x, sw.y, sw.species_id)
        populations[key] = populations.get(key, 0) + sw.population
    return populations


def _co_located_swarm_population(
    world: ECSWorld,
    x: int,
    y: int,
    herbivore_species_id: int,
) -> int:
    """Return total population of a herbivore species at one grid cell.

    Args:
        world: ECSWorld used for spatial hash lookup.
        x: The X-axis spatial grid coordinate.
        y: The Y-axis spatial grid coordinate.
        herbivore_species_id: Herbivore species to aggregate.

    Returns:
        Sum of populations for matching swarms at ``(x, y)``.
    """
    total_population = 0
    cell_entities = world.entities_at(x, y)
    if not cell_entities:
        return 0
    for co_eid in cell_entities:
        co_entity = world._entities.get(co_eid)
        if co_entity is None:
            continue
        swarm = co_entity.get_component(SwarmComponent) if co_entity.has_component(SwarmComponent) else None
        if swarm is not None and swarm.species_id == herbivore_species_id:
            total_population += swarm.population
    return total_population


def _collect_mycorrhizal_targets(
    source_plant: PlantComponent,
    world: ECSWorld,
    mycorrhizal_inter_species: bool,
) -> list[PlantComponent]:
    """Return relay-eligible neighbouring plants connected via mycorrhiza.

    Args:
        source_plant: Originating plant component.
        world: ECSWorld for neighbour lookup.
        mycorrhizal_inter_species: Whether cross-species relay is allowed.

    Returns:
        Relay targets that are alive and species-compatible.
    """
    targets: list[PlantComponent] = []
    for neighbour_id in source_plant.mycorrhizal_connections:
        if not world.has_entity(neighbour_id):
            continue
        neighbour_entity = world.get_entity(neighbour_id)
        if not neighbour_entity.has_component(PlantComponent):
            continue
        neighbour = neighbour_entity.get_component(PlantComponent)
        if not mycorrhizal_inter_species and neighbour.species_id != source_plant.species_id:
            continue
        targets.append(neighbour)
    return targets


def toroidal_distance(x1: int, y1: int, x2: int, y2: int, width: int, height: int) -> float:
    """Calculate shortest Euclidean distance across a toroidal grid seam.

    Args:
        x1: X coordinate of first point.
        y1: Y coordinate of first point.
        x2: X coordinate of second point.
        y2: Y coordinate of second point.
        width: Grid width.
        height: Grid height.

    Returns:
        float: Shortest distance considering wrap-around boundary.
    """
    return toroidal_distance_jit(x1, y1, x2, y2, width, height)
