# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Unit tests for the live dashboard payload presenter.

Verifies that the dashboard JSON payload adheres exactly to the frontend
API contract, preventing visual regressions on the UI dashboard.
"""

from phids.api.presenters.dashboard.payloads import build_live_dashboard_payload
from phids.api.schemas.simulation import SimulationConfig
from phids.api.schemas.species import (
    DietCompatibilityMatrix,
    FloraSpeciesParams,
    HerbivoreSpeciesParams,
)
from phids.engine.loop import SimulationLoop


def test_payload_contract_strictness() -> None:
    """Verify that the dashboard payload matches the required contract exactly to prevent visual breakages."""
    config = SimulationConfig(
        grid_width=8,
        grid_height=8,
        flora_species=[
            FloraSpeciesParams(
                species_id=0,
                name="F",
                max_energy=10,
                growth_rate=1,
                survival_threshold=1,
                reproduction_interval=1,
                base_energy=1,
                seed_cost=1,
            )
        ],
        herbivore_species=[
            HerbivoreSpeciesParams(
                species_id=0,
                name="H",
                energy_min=1,
                velocity=1,
                consumption_rate=1,
                energy_max=1,
                energy_initial=1,
                metabolism_upkeep=1,
            )
        ],
        num_signals=2,
        num_toxins=2,
        diet_matrix=DietCompatibilityMatrix(rows=[[True]]),
    )
    loop = SimulationLoop(config)

    payload = build_live_dashboard_payload(loop, substance_names={})

    # 1. Top Level Keys Verification
    expected_top_level_keys = {
        "contract_version",
        "tick",
        "grid_width",
        "grid_height",
        "max_energy",
        "plant_energy",
        "species_energy",
        "all_flora_species",
        "signal_overlay",
        "toxin_overlay",
        "max_signal",
        "max_toxin",
        "plants",
        "mycorrhizal_links",
        "swarms",
        "terminated",
        "termination_reason",
        "running",
        "paused",
    }
    assert set(payload.keys()) == expected_top_level_keys

    # 2. Plant Column Verification
    expected_plant_columns = {
        "entity_id",
        "species_id",
        "name",
        "x",
        "y",
        "energy",
        "root_link_count",
        "active_signal_ids",
        "active_toxin_ids",
    }
    assert set(payload["plants"].keys()) == expected_plant_columns

    # 3. Swarm Column Verification
    expected_swarm_columns = {
        "x",
        "y",
        "population",
        "species_id",
        "name",
        "energy",
        "energy_deficit",
        "repelled",
        "repelled_ticks_remaining",
        "toxin_level",
        "intoxicated",
    }
    assert set(payload["swarms"].keys()) == expected_swarm_columns
