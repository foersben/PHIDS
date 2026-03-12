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
    config = load_scenario_from_json(path)

    assert config.initial_plants, f"{path.name} should include plant placements"
    assert config.initial_swarms, f"{path.name} should include herbivore placements"
    assert len(config.flora_species) <= 16
    assert len(config.predator_species) <= 16


@pytest.mark.asyncio
@pytest.mark.parametrize("path", EXAMPLE_PATHS, ids=lambda path: path.stem)
async def test_example_scenarios_step_without_runtime_errors(path: Path) -> None:
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
    configs = [load_scenario_from_json(path) for path in EXAMPLE_PATHS]
    example_stems = {path.stem for path in EXAMPLE_PATHS}

    assert example_stems == CURATED_EXAMPLE_STEMS
    assert any(config.mycorrhizal_inter_species for config in configs)
    assert any(not config.mycorrhizal_inter_species for config in configs)


def test_dry_shrubland_cycles_preserves_predator_reproduction_divisors() -> None:
    config = load_scenario_from_json(EXAMPLES_DIR / "dry_shrubland_cycles.json")
    loop = SimulationLoop(config)

    divisors = sorted(
        swarm.reproduction_energy_divisor
        for entity in loop.world.query(SwarmComponent)
        for swarm in [entity.get_component(SwarmComponent)]
    )

    assert divisors == [0.9, 0.9, 1.15]
