"""Experimental validation suite for test logging.

This module defines hypothesis-driven checks for deterministic ecosystem behavior, API constraints, and simulation invariants. The tests map computational rules to biological interpretations, including metabolic attrition, trigger-gated signaling, and O(1) spatial locality assumptions, to ensure that implementation details remain aligned with the PHIDS scientific model.
"""

from __future__ import annotations

import asyncio
import logging

from phids.api.schemas import (
    DietCompatibilityMatrix,
    FloraSpeciesParams,
    InitialPlantPlacement,
    InitialSwarmPlacement,
    PredatorSpeciesParams,
    SimulationConfig,
)
from phids.api.ui_state import DraftState
from phids.engine.loop import SimulationLoop
from phids.shared.logging_config import configure_logging, get_simulation_debug_interval


def _base_config(max_ticks: int = 20) -> SimulationConfig:
    return SimulationConfig(
        grid_width=8,
        grid_height=8,
        max_ticks=max_ticks,
        tick_rate_hz=50.0,
        num_signals=2,
        num_toxins=2,
        wind_x=0.0,
        wind_y=0.0,
        flora_species=[
            FloraSpeciesParams(
                species_id=0,
                name="flora-0",
                base_energy=8.0,
                max_energy=30.0,
                growth_rate=2.0,
                survival_threshold=1.0,
                reproduction_interval=3,
                seed_min_dist=1.0,
                seed_max_dist=2.0,
                seed_energy_cost=1.0,
                triggers=[],
            )
        ],
        predator_species=[
            PredatorSpeciesParams(
                species_id=0,
                name="pred-0",
                energy_min=1.0,
                velocity=1,
                consumption_rate=1.0,
            )
        ],
        diet_matrix=DietCompatibilityMatrix(rows=[[True]]),
        initial_plants=[InitialPlantPlacement(species_id=0, x=2, y=2, energy=10.0)],
        initial_swarms=[InitialSwarmPlacement(species_id=0, x=2, y=2, population=3, energy=3.0)],
    )


def test_configure_logging_respects_env(monkeypatch) -> None:
    """Validates the configure logging respects env invariant and confirms the expected biological behavior under controlled simulation conditions.

    The assertions in this test enforce deterministic state transitions so ecological outcomes remain consistent with configured constraints and signal-response dynamics.

    Args:
        monkeypatch: Input value used to parameterize deterministic behavior for this callable.

    Returns:
        None. The function verifies invariant compliance through assertions rather than data return.

    """
    monkeypatch.setenv("PHIDS_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("PHIDS_LOG_SIM_DEBUG_INTERVAL", "7")

    configure_logging(force=True)

    assert logging.getLogger("phids").getEffectiveLevel() == logging.DEBUG
    assert logging.getLogger("phids").getEffectiveLevel() == logging.DEBUG
    assert get_simulation_debug_interval() == 7


def test_draft_build_logs_missing_species_warning(caplog) -> None:
    """Validates the draft build logs missing species warning invariant and confirms the expected biological behavior under controlled simulation conditions.

    The assertions in this test enforce deterministic state transitions so ecological outcomes remain consistent with configured constraints and signal-response dynamics.

    Args:
        caplog: Input value used to parameterize deterministic behavior for this callable.

    Returns:
        None. The function verifies invariant compliance through assertions rather than data return.

    """
    draft = DraftState(flora_species=[], predator_species=[])

    with caplog.at_level(logging.WARNING, logger="phids.api.ui_state"):
        try:
            draft.build_sim_config()
        except ValueError:
            pass

    assert "Draft build rejected because required species are missing" in caplog.text


def test_simulation_loop_emits_periodic_debug_summary(monkeypatch, caplog) -> None:
    """Validates the simulation loop emits periodic debug summary invariant and confirms the expected biological behavior under controlled simulation conditions.

    The assertions in this test enforce deterministic state transitions so ecological outcomes remain consistent with configured constraints and signal-response dynamics.

    Args:
        monkeypatch: Input value used to parameterize deterministic behavior for this callable.
        caplog: Input value used to parameterize deterministic behavior for this callable.

    Returns:
        None. The function verifies invariant compliance through assertions rather than data return.

    """
    loop = SimulationLoop(_base_config(max_ticks=30))
    loop._debug_tick_interval = 1

    with caplog.at_level(logging.DEBUG, logger="phids.engine.loop"):
        result = asyncio.run(loop.step())

    assert result.terminated is False
    assert "Tick summary" in caplog.text
