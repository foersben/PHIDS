# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Swarms live cell details extraction."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from phids.engine.components.swarm import SwarmComponent


def _build_live_swarm_payload(
    swarm: SwarmComponent,
    herbivore_names: dict[int, str],
    herbivore_params: dict[int, Any] | None = None,
    cell_toxin_peak: float = 0.0,
    cell_signal_peak: float = 0.0,
    cell_plant_energy: float = 0.0,
) -> dict[str, object]:
    """Helper to construct the detailed live swarm presentation structure.

    Args:
        swarm: The swarm component.
        herbivore_names: The herbivore names.
        herbivore_params: Optional mapping of species_id to species params schema.
        cell_toxin_peak: The toxin peak in the cell.
        cell_signal_peak: The signal peak in the cell.
        cell_plant_energy: Available plant energy in the cell.

    Returns:
        The presentation structure.
    """
    sp_params = herbivore_params.get(swarm.species_id) if herbivore_params else None
    inc_factor = sp_params.incidental_mortality_factor if sp_params else 0.0
    inc_mode = sp_params.incidental_mortality_mode if sp_params else "trampling"
    upkeep_per_ind = sp_params.energy_upkeep_per_individual if sp_params else 0.05
    total_upkeep = swarm.population * upkeep_per_ind

    # MVT Full Belly lock heuristic
    is_anchored = (cell_plant_energy >= total_upkeep and total_upkeep > 0.0) if cell_plant_energy > 0.0 else False
    min_energy_threshold = swarm.population * swarm.energy_min

    return {
        "entity_id": swarm.entity_id,
        "species_id": swarm.species_id,
        "name": herbivore_names.get(swarm.species_id, f"Herbivore {swarm.species_id}"),
        "population": swarm.population,
        "initial_population": swarm.initial_population,
        "energy": swarm.energy,
        "energy_min": swarm.energy_min,
        "energy_deficit": max(0.0, min_energy_threshold - swarm.energy),
        "starvation_threshold": min_energy_threshold,
        "energy_label": f"{swarm.energy:.1f} (Min: {min_energy_threshold:.1f})",
        "total_metabolic_upkeep": total_upkeep,
        "is_anchored_feeding": is_anchored,
        "incidental_mortality_factor": inc_factor,
        "incidental_mortality_mode": inc_mode,
        "mitosis_progress": (
            swarm.population / swarm.split_population_threshold if swarm.split_population_threshold > 0 else None
        ),
        "mitosis_label": (
            f"{swarm.population} / {swarm.split_population_threshold}"
            f" ({100.0 * swarm.population / swarm.split_population_threshold:.0f}%)"
            if swarm.split_population_threshold > 0
            else "No threshold"
        ),
        "repelled": swarm.repelled,
        "repelled_ticks_remaining": swarm.repelled_ticks_remaining,
        "intoxicated": cell_toxin_peak > 0.0,
        "signal_level": cell_signal_peak,
        "toxin_level": cell_toxin_peak,
    }
