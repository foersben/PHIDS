# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Unit tests for the live dashboard payload presenter.

Verifies that the dashboard JSON payload adheres exactly to the frontend
API contract, preventing visual regressions on the UI dashboard.
"""

from dataclasses import FrozenInstanceError

import pytest

from phids.api.presenters.dashboard.payloads import (
    PlantMetrics,
    _compute_plant_metrics,
    build_live_dashboard_payload,
    extract_ui_snapshot,
)
from phids.api.schemas.simulation import SimulationConfig
from phids.api.schemas.species import (
    DietCompatibilityMatrix,
    FloraSpeciesParams,
    HerbivoreSpeciesParams,
)
from phids.engine.components.plant import PlantComponent
from phids.engine.loop import SimulationLoop


def test_payload_contract_strictness() -> None:
    """Verify that the dashboard payload matches the required contract exactly to prevent visual breakages."""
    config = SimulationConfig(
        grid_width=16,
        grid_height=16,
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

    payload = build_live_dashboard_payload(extract_ui_snapshot(loop), substance_names={})

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
        "max_energy",
        "structural_mass",
        "max_structural_mass",
        "fragility_pct",
        "incidental_risk_level",
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


def test_compute_plant_metrics_returns_frozen_dataclass() -> None:
    """Verify _compute_plant_metrics returns a frozen PlantMetrics dataclass with expected attributes."""
    plant = PlantComponent(
        entity_id=1,
        species_id=0,
        x=2,
        y=3,
        energy=50.0,
        max_energy=100.0,
        base_energy=10.0,
        growth_rate=1.0,
        survival_threshold=5.0,
        reproduction_interval=10,
        seed_min_dist=1.0,
        seed_max_dist=3.0,
        seed_energy_cost=10.0,
        structural_mass=25.0,
        max_structural_mass=100.0,
    )

    metrics = _compute_plant_metrics(plant)

    assert isinstance(metrics, PlantMetrics)
    assert metrics.structural_mass == 25.0
    assert metrics.max_structural_mass == 100.0
    assert metrics.fragility_pct == 75.0
    assert metrics.incidental_risk_level == "High Risk"
    assert metrics.risk_level == "High Risk"

    # Verify frozen immutability
    with pytest.raises(FrozenInstanceError):
        metrics.structural_mass = 50.0  # type: ignore[misc]
