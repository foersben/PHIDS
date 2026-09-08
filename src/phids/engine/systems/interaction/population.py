# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Population utilities for interaction system."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import numpy.typing as npt
from numba import njit

from phids.engine.components.swarm import SwarmComponent
from phids.shared.constants import TILE_CARRYING_CAPACITY as TILE_CARRYING_CAPACITY

if TYPE_CHECKING:
    from phids.engine.core.ecs import ECSWorld


@njit(cache=True)
def _accumulate_tile_population_jit_pow2(
    tile_populations: npt.NDArray[np.int32],
    x: int,
    y: int,
    width: int,
    mask_x: int,
    mask_y: int,
    delta: int,
) -> None:
    """Numba-compiled helper for power-of-two grids using bitwise wrapping without branches."""
    idx = (y & mask_y) * width + (x & mask_x)
    tile_populations[idx] += delta


@njit(cache=True)
def _accumulate_tile_population_jit(
    tile_populations: npt.NDArray[np.int32],
    x: int,
    y: int,
    width: int,
    height: int,
    delta: int,
) -> None:
    """Numba-compiled helper to apply population delta branchlessly with bounds gating."""
    valid = (x >= 0) & (x < width) & (y >= 0) & (y < height)
    safe_x = x if valid else 0
    safe_y = y if valid else 0
    safe_delta = delta if valid else 0
    tile_populations[safe_y * width + safe_x] += safe_delta


def _accumulate_tile_population(
    tile_populations: npt.NDArray[np.int32] | list[int],
    x: int,
    y: int,
    width: int,
    delta: int,
    height: int = 0,
) -> None:
    """Apply a signed population delta to one tile-population cache entry.

    This function maintains a lightweight, tick-local census of aggregate swarm populations per
    grid cell. The cache is used as an O(1) crowding-pressure oracle: rather than re-querying the
    spatial hash and summing component populations on every crowding check, each movement and
    reproduction event issues a corrective delta to keep the cache consistent. The function is
    intentionally side-effecting and operates in-place on the shared ``tile_populations`` flat
    list passed by the outer interaction loop, which pre-allocates WxH capacity for cache locality.

    Args:
        tile_populations: Mutable flat list mapping (y * w + x) to total individual counts,
            shared across all swarm iterations within a single ``run_interaction`` call.
        x: Grid column index of the cell to update.
        y: Grid row index of the cell to update.
        width: Grid width to compute the flat index.
        delta: Signed integer change in population count; positive for births or arrivals,
            negative for deaths or departures.
        height: Optional grid height for JIT boundary checks.

    """
    if isinstance(tile_populations, np.ndarray):
        h = height if height > 0 else (len(tile_populations) // width if width > 0 else 0)
        if (width & (width - 1) == 0) and (h & (h - 1) == 0) and width > 0 and h > 0 and 0 <= x < width and 0 <= y < h:
            _accumulate_tile_population_jit_pow2(tile_populations, x, y, width, width - 1, h - 1, delta)
        else:
            _accumulate_tile_population_jit(tile_populations, x, y, width, h, delta)
    elif 0 <= x < width and y >= 0:
        try:
            tile_populations[y * width + x] += delta
        except IndexError:
            pass


def _co_located_swarm_population(world: ECSWorld, x: int, y: int) -> int:
    """Return the total individual population of all swarms occupying a single grid cell.

    This function performs a local density census by iterating over all entity identifiers
    registered at the specified cell via the O(1) spatial hash, accumulating the population
    count of every entity that carries a ``SwarmComponent``. The result quantifies the aggregate
    occupancy load of the cell, which is compared against ``TILE_CARRYING_CAPACITY`` to determine
    whether interference-competition-driven dispersal should be initiated. The check is performed
    on-demand rather than from the tick-local cache when an authoritative count is required
    outside the main loop context. Entities absent from the ECS registry (stale spatial hash
    entries scheduled for garbage collection) are gracefully skipped to preserve census accuracy
    in the presence of concurrent mortality.

    Args:
        world: The ECS world registry providing both spatial hash lookups and component access.
        x: Grid column index of the cell to census.
        y: Grid row index of the cell to census.

    Returns:
        The non-negative integer sum of ``SwarmComponent.population`` across all live swarm
        entities co-located at ``(x, y)``, representing the instantaneous local population
        density for crowding-pressure evaluation.

    """
    total_population = 0
    for entity_id in world.entities_at(x, y):
        if not world.has_entity(entity_id):
            continue
        entity = world.get_entity(entity_id)
        if entity.has_component(SwarmComponent):
            swarm = entity.get_component(SwarmComponent)
            total_population += swarm.population
    return total_population
