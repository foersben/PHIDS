# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Draft-state mutation module for biotope parameters.

This module provides pure functions for updating the global biotope settings of a draft
scenario, including grid dimensions, termination thresholds, and atmospheric factors.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from phids.api.ui_state import DraftState

    pass


def update_biotope(
    draft: DraftState,
    *,
    grid_width: int,
    grid_height: int,
    max_ticks: int,
    tick_rate_hz: float,
    wind_x: float,
    wind_y: float,
    num_signals: int,
    num_toxins: int,
    z2_flora_species_extinction: int,
    z4_herbivore_species_extinction: int,
    z6_max_total_flora_energy: float,
    z7_max_total_herbivore_population: int,
    mycorrhizal_inter_species: bool,
    mycorrhizal_connection_cost: float,
    mycorrhizal_growth_interval_ticks: int,
    mycorrhizal_signal_velocity: int,
    signal_decay_factor: float = 0.85,
    substance_emit_rate: float = 0.1,
) -> bool:
    """Normalize and persist global biotope parameters into the draft.

    Args:
        draft: Draft state mutated in place.
        grid_width: Requested biotope width.
        grid_height: Requested biotope height.
        max_ticks: Requested simulation tick horizon.
        tick_rate_hz: Requested UI stream rate.
        wind_x: Requested uniform wind x-component.
        wind_y: Requested uniform wind y-component.
        num_signals: Requested number of signal layers.
        num_toxins: Requested number of toxin layers.
        z2_flora_species_extinction: Requested species-specific flora-extinction termination rule.
        z4_herbivore_species_extinction: Requested species-specific herbivore-extinction rule.
        z6_max_total_flora_energy: Requested upper bound for total flora energy termination.
        z7_max_total_herbivore_population: Requested upper bound for herbivore population
            termination.
        mycorrhizal_inter_species: Requested root-link species policy.
        mycorrhizal_connection_cost: Requested root-link establishment cost.
        mycorrhizal_growth_interval_ticks: Requested root-growth interval.
        mycorrhizal_signal_velocity: Requested root-network signal velocity.
        signal_decay_factor: Requested per-tick airborne signal retention (0.0-1.0).
        substance_emit_rate: Requested concentration increment per active emit tick (0.0-1.0).

    Returns:
        ``True`` when at least one submitted scalar required clamping.

    """
    clamped_grid_width = max(10, min(200, grid_width))
    clamped_grid_height = max(10, min(200, grid_height))
    clamped_max_ticks = max(1, max_ticks)
    clamped_tick_rate_hz = max(0.1, tick_rate_hz)
    clamped_num_signals = max(1, min(16, num_signals))
    clamped_num_toxins = max(1, min(16, num_toxins))
    clamped_z2 = max(-1, min(15, z2_flora_species_extinction))
    clamped_z4 = max(-1, min(15, z4_herbivore_species_extinction))
    clamped_z6 = max(-1.0, z6_max_total_flora_energy)
    clamped_z7 = max(-1, z7_max_total_herbivore_population)
    clamped_connection_cost = max(0.0, mycorrhizal_connection_cost)
    clamped_growth_interval = max(1, min(256, mycorrhizal_growth_interval_ticks))
    clamped_signal_velocity = max(1, mycorrhizal_signal_velocity)
    clamped_signal_decay = max(0.01, min(1.0, signal_decay_factor))
    clamped_substance_emit = max(0.01, min(1.0, substance_emit_rate))

    draft.grid_width = clamped_grid_width
    draft.grid_height = clamped_grid_height
    draft.max_ticks = clamped_max_ticks
    draft.tick_rate_hz = clamped_tick_rate_hz
    draft.wind_x = wind_x
    draft.wind_y = wind_y
    draft.num_signals = clamped_num_signals
    draft.num_toxins = clamped_num_toxins
    draft.z2_flora_species_extinction = clamped_z2
    draft.z4_herbivore_species_extinction = clamped_z4
    draft.z6_max_total_flora_energy = clamped_z6
    draft.z7_max_total_herbivore_population = clamped_z7
    draft.mycorrhizal_inter_species = mycorrhizal_inter_species
    draft.mycorrhizal_connection_cost = clamped_connection_cost
    draft.mycorrhizal_growth_interval_ticks = clamped_growth_interval
    draft.mycorrhizal_signal_velocity = clamped_signal_velocity
    draft.signal_decay_factor = clamped_signal_decay
    draft.substance_emit_rate = clamped_substance_emit

    return any(
        (
            clamped_grid_width != grid_width,
            clamped_grid_height != grid_height,
            clamped_max_ticks != max_ticks,
            clamped_tick_rate_hz != tick_rate_hz,
            clamped_num_signals != num_signals,
            clamped_num_toxins != num_toxins,
            clamped_z2 != z2_flora_species_extinction,
            clamped_z4 != z4_herbivore_species_extinction,
            clamped_z6 != z6_max_total_flora_energy,
            clamped_z7 != z7_max_total_herbivore_population,
            clamped_connection_cost != mycorrhizal_connection_cost,
            clamped_growth_interval != mycorrhizal_growth_interval_ticks,
            clamped_signal_velocity != mycorrhizal_signal_velocity,
            clamped_signal_decay != signal_decay_factor,
            clamped_substance_emit != substance_emit_rate,
        )
    )
