# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Zarr replay buffer disk serialization vs live engine tick parity integration tests."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from phids.api.schemas.simulation import SimulationConfig
from phids.api.schemas.species import FloraSpeciesParams, HerbivoreResistancesSchema, HerbivoreSpeciesParams
from phids.api.schemas.triggers import PassiveDefensesSchema
from phids.engine.loop import SimulationLoop
from phids.io.zarr_replay import ReplayBuffer

try:
    import zarr  # noqa: F401

    ZARR_AVAILABLE = True
except ImportError:
    ZARR_AVAILABLE = False


@pytest.mark.skipif(not ZARR_AVAILABLE, reason="zarr library required for replay testing")
@pytest.mark.scientific_invariant
@pytest.mark.asyncio
async def test_zarr_replay_disk_serialization_live_parity(tmp_path: Path) -> None:
    """Assert Zarr disk replay buffer retains 100% array state parity with live engine execution."""
    flora = FloraSpeciesParams(
        species_id=0,
        name="F0",
        base_energy=10,
        max_energy=100,
        growth_rate=5,
        survival_threshold=0,
        reproduction_interval=10,
        passive_defenses=PassiveDefensesSchema(digestibility_modifier=1.0, mechanical_damage_per_bite=0.0),
    )
    herbivore = HerbivoreSpeciesParams(
        species_id=0,
        name="H0",
        energy_min=1,
        velocity=1,
        consumption_rate=4.0,
        energy_upkeep_per_individual=0.1,
        resistances=HerbivoreResistancesSchema(digestive_efficiency=1.0, morphological_adaptation=0.0),
    )
    config = SimulationConfig(
        grid_width=16,
        grid_height=16,
        flora_species=[flora],
        herbivore_species=[herbivore],
        diet_matrix={"rows": [[True]]},
    )
    loop = SimulationLoop(config, disable_replay=False)

    store_path = tmp_path / "parity_test.zarr"
    replay_buf = ReplayBuffer(spill_path=store_path)

    live_snapshots: list[dict[str, np.ndarray]] = []

    for idx in range(5):
        _ = await loop.step()

        # Capture live state snapshot
        state = {
            "tick": idx,
            "plant_energy": loop.env.plant_energy_layer.copy(),
            "apparent_nutrition": loop.env.apparent_nutrition_layer.copy(),
        }
        live_snapshots.append(state)
        replay_buf.append(state)

    export_path = tmp_path / "export.zarr"
    replay_buf.save(export_path)

    # Load back from Zarr disk store
    loaded_buf = ReplayBuffer.load(export_path)
    assert len(loaded_buf) == len(live_snapshots)

    for idx, expected_state in enumerate(live_snapshots):
        frame = loaded_buf.get_frame(idx)
        np.testing.assert_array_equal(
            frame["plant_energy"],
            expected_state["plant_energy"],
            err_msg=f"Tick {idx} plant_energy matrix parity failure",
        )
        np.testing.assert_array_equal(
            frame["apparent_nutrition"],
            expected_state["apparent_nutrition"],
            err_msg=f"Tick {idx} apparent_nutrition matrix parity failure",
        )
