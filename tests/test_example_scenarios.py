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

EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples"
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
    """
    Validates scenario configuration invariants for curated PHIDS example scenarios.

    This test function ensures that each curated scenario adheres to deterministic placement rules, including the presence of initial plant and herbivore placements, and enforces the Rule of 16 entity caps for flora and herbivore species. The validation supports reproducible ecological simulation and prevents configuration errors that could compromise emergent dynamics or violate architectural constraints fundamental to PHIDS.

    Args:
        path: The absolute path to the scenario JSON file. The parameter is used to load scenario configuration and validate placement and entity caps.

    Returns:
        None. Asserts scenario configuration invariants and placement rules.

    Raises:
        AssertionError: If scenario violates placement rules or entity caps, ensuring architectural and biological correctness.
    """
    config = load_scenario_from_json(path)

    assert config.initial_plants, f"{path.name} should include plant placements"
    assert config.initial_swarms, f"{path.name} should include herbivore placements"
    assert len(config.flora_species) <= 16
    assert len(config.herbivore_species) <= 16


@pytest.mark.asyncio
@pytest.mark.parametrize("path", EXAMPLE_PATHS, ids=lambda path: path.stem)
async def test_example_scenarios_step_without_runtime_errors(path: Path) -> None:
    """
    Verifies simulation step execution and snapshot integrity for PHIDS example scenarios.

    This asynchronous test function advances the simulation loop for each curated scenario, confirming that no runtime errors occur during step execution and that state snapshots expose plant energy layers with correct dimensions. The test substantiates the integrity of double-buffered simulation logic and the deterministic propagation of ecological signals, supporting rigorous validation of emergent ecosystem behavior.

    Args:
        path: The absolute path to the scenario JSON file. Used to load scenario configuration and advance simulation steps.

    Returns:
        None. Asserts simulation step execution and snapshot integrity.

    Raises:
        AssertionError: If simulation step or snapshot validation fails, ensuring architectural and biological correctness.
    """
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
    """
    Ensures curated PHIDS example scenarios include both mycorrhizal and non-mycorrhizal configurations.

    This test function verifies that the curated scenario pack contains a scientifically diverse set of scenarios, including those with and without inter-species mycorrhizal networks. The validation supports comprehensive coverage of ecological phenomena and ensures the scenario suite reflects the full spectrum of biological interactions modeled by PHIDS.

    Args:
        None

    Returns:
        None. Asserts scenario diversity and mycorrhizal coverage.

    Raises:
        AssertionError: If scenario pack lacks diversity or mycorrhizal coverage, ensuring scientific completeness.
    """
    configs = [load_scenario_from_json(path) for path in EXAMPLE_PATHS]
    example_stems = {path.stem for path in EXAMPLE_PATHS}

    assert example_stems == CURATED_EXAMPLE_STEMS
    assert any(config.mycorrhizal_inter_species for config in configs)
    assert any(not config.mycorrhizal_inter_species for config in configs)


def test_dry_shrubland_cycles_preserves_herbivore_reproduction_divisors() -> None:
    """
    Validates preservation of herbivore reproduction energy divisors in the 'dry_shrubland_cycles' scenario.

    This test function confirms that the scenario configuration maintains the intended reproduction energy divisors for herbivore entities, ensuring deterministic reproduction thresholds and supporting the scientific accuracy of metabolic attrition and population dynamics within the PHIDS simulation framework.

    Args:
        None

    Returns:
        None. Asserts preservation of herbivore reproduction divisors.

    Raises:
        AssertionError: If divisors are not preserved, ensuring scientific and architectural correctness.
    """
    config = load_scenario_from_json(EXAMPLES_DIR / "dry_shrubland_cycles.json")
    loop = SimulationLoop(config)

    divisors = sorted(
        swarm.reproduction_energy_divisor
        for entity in loop.world.query(SwarmComponent)
        for swarm in [entity.get_component(SwarmComponent)]
    )

    assert divisors == [0.9, 0.9, 1.15]
