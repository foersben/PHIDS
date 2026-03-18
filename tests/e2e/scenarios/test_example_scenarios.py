"""
Test coverage for PHIDS curated example scenarios and scenario validation invariants.

This module implements integration tests for PHIDS curated example scenarios. The test suite verifies scenario loading, placement validation, and simulation step execution, ensuring compliance with deterministic scenario construction, Rule of 16 entity caps, and double-buffered simulation logic. Each test function is documented to state the invariant or biological behavior being validated and its scientific rationale, supporting reproducible and rigorous validation of emergent ecological dynamics and scenario configuration. The module-level docstring is written in accordance with Google-style documentation standards, providing a comprehensive scholarly abstract of the test suite's scope and scientific rationale.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from phids.engine.components.swarm import SwarmComponent
from phids.engine.loop import SimulationLoop
from phids.io.scenario import load_scenario_from_json

EXAMPLES_DIR = Path(__file__).resolve().parents[3] / "examples"
EXAMPLE_PATHS = sorted(EXAMPLES_DIR.glob("*.json"))
CURATED_EXAMPLE_STEMS = {
    "dry_shrubland_cycles",
    "meadow_defense",
    "mixed_forest_understory",
    "rectangular_crossfire",
    "root_network_alarm_chain",
    "wind_tunnel_orchard",
}


@pytest.mark.parametrize("path", EXAMPLE_PATHS, ids=lambda path: path.stem)
def test_example_scenarios_validate(path: Path) -> None:
    """Verify each curated scenario has initial placements and respects Rule-of-16 species caps."""
    config = load_scenario_from_json(path)

    assert config.initial_plants, f"{path.name} should include plant placements"
    assert config.initial_swarms, f"{path.name} should include herbivore placements"
    assert len(config.flora_species) <= 16
    assert len(config.herbivore_species) <= 16


@pytest.mark.asyncio
@pytest.mark.parametrize("path", EXAMPLE_PATHS, ids=lambda path: path.stem)
async def test_example_scenarios_step_without_runtime_errors(path: Path) -> None:
    """Verify curated scenarios step without runtime errors and expose consistent snapshot dimensions."""
    config = load_scenario_from_json(path)
    loop = SimulationLoop(config)

    for _ in range(min(12, config.max_ticks)):
        result = await loop.step()
        snapshot = loop.get_state_snapshot()
        assert snapshot["tick"] == loop.tick
        assert snapshot["plant_energy_layer"], (
            f"{path.name} should expose plant energy in snapshots"
        )
        assert len(snapshot["plant_energy_layer"]) == config.grid_width
        assert len(snapshot["plant_energy_layer"][0]) == config.grid_height
        if result.terminated:
            break


def test_example_pack_mixes_mycorrhizal_and_non_mycorrhizal_scenarios() -> None:
    """Verify the curated pack includes both inter-species and isolated mycorrhizal configurations."""
    configs = [load_scenario_from_json(path) for path in EXAMPLE_PATHS]
    example_stems = {path.stem for path in EXAMPLE_PATHS}

    assert example_stems == CURATED_EXAMPLE_STEMS
    assert any(config.mycorrhizal_inter_species for config in configs)
    assert any(not config.mycorrhizal_inter_species for config in configs)


def test_dry_shrubland_cycles_preserves_herbivore_reproduction_divisors() -> None:
    """Verify `dry_shrubland_cycles` keeps configured herbivore reproduction divisors."""
    config = load_scenario_from_json(EXAMPLES_DIR / "dry_shrubland_cycles.json")
    loop = SimulationLoop(config)

    divisors = sorted(
        swarm.reproduction_energy_divisor
        for entity in loop.world.query(SwarmComponent)
        for swarm in [entity.get_component(SwarmComponent)]
    )

    assert divisors == [0.9, 0.9, 1.15]
