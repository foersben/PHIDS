# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Evaluation logic for signaling triggers.

Hot-Path Import Resolution & Dynamic Module Overhead:
------------------------------------------------------------------
In interpreted high-level runtimes, dynamic `import` statements executed inside inner loop functions
incur non-trivial overhead. Each function-local import requires querying Python's global `sys.modules`
hash dictionary, verifying module locks, and performing frame attribute resolution.

In signaling evaluation loops operating across thousands of plant entities per tick
(O(N_plants * M_triggers)), dynamic import resolution introduces instruction cache churn and
dictionary lookup latency. Hoisting schema and component imports to module top-level resolves
symbols once at initial module load, allowing the interpreter to execute inner loops with direct
global variable access.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from numba import njit

from phids.api.schemas.triggers import EnvironmentalSignalInitiator, HerbivoreAttackInitiator

if TYPE_CHECKING:
    import numpy as np
    import numpy.typing as npt

    from phids.engine.components.plant import PlantComponent
    from phids.engine.core.biotope import GridEnvironment
    from phids.engine.systems.signaling.spatial import SwarmPopulationIndex
    from phids.engine.systems.signaling.types import CompiledTrigger


@njit(cache=True, fastmath=True)
def _evaluate_environmental_initiator_njit(
    xs: npt.NDArray[np.int32],
    ys: npt.NDArray[np.int32],
    signal_layer: npt.NDArray[np.float64],
    response_curve: int,
    min_concentration: float,
    half_saturation: float,
    hill_cooperativity: float,
    out_mask: npt.NDArray[np.bool_],
) -> None:
    """Evaluates environmental signal concentration against initiator parameters in a Numba jitted loop.

    Args:
        xs: Array of x-coordinates of the plants to evaluate.
        ys: Array of y-coordinates of the plants to evaluate.
        signal_layer: The dense spatial grid array for the signal.
        response_curve: An integer representing the response curve type (0: step, 1: hill, 2: logarithmic).
        min_concentration: The minimum concentration required to trigger a response.
        half_saturation: The half-saturation parameter for the Hill function.
        hill_cooperativity: The cooperativity parameter for the Hill function.
        out_mask: Boolean array updated in-place with evaluation results.
    """
    for i in range(len(xs)):
        x = xs[i]
        y = ys[i]
        conc = signal_layer[x, y]

        if response_curve == 0:  # step
            out_mask[i] = conc >= min_concentration
        elif response_curve == 1:  # hill
            if conc > 0.0:
                cn = conc**hill_cooperativity
                priming_factor = cn / (half_saturation**hill_cooperativity + cn)
                out_mask[i] = priming_factor >= 0.05
            else:
                out_mask[i] = False
        elif response_curve == 2:  # logarithmic
            out_mask[i] = conc >= min_concentration
        else:
            out_mask[i] = False


@njit(cache=True, fastmath=True)
def _evaluate_herbivore_initiator_njit(
    xs: npt.NDArray[np.int32],
    ys: npt.NDArray[np.int32],
    species_id: int,
    min_population: int,
    swarm_grid: npt.NDArray[np.int32],
    out_mask: npt.NDArray[np.bool_],
) -> None:
    """Evaluates herbivore initiator thresholds in a Numba jitted loop.

    Args:
        xs: Array of x-coordinates of the plants to evaluate.
        ys: Array of y-coordinates of the plants to evaluate.
        species_id: The ID of the herbivore species acting as the trigger.
        min_population: The minimum population required to trigger a response.
        swarm_grid: The spatial grid containing herbivore swarm populations.
        out_mask: Boolean array updated in-place with evaluation results.
    """
    for i in range(len(xs)):
        x = xs[i]
        y = ys[i]
        pop = swarm_grid[species_id, x, y]
        out_mask[i] = pop >= min_population


def _evaluate_environmental_signal(
    initiator: EnvironmentalSignalInitiator,
    plant: PlantComponent,
    env: GridEnvironment,
) -> bool:
    """Evaluates whether a plant's environmental conditions meet an initiator's thresholds.

    Args:
        initiator: The initiator configuration for the signal.
        plant: The plant component experiencing the signal.
        env: The grid environment containing signal layers.

    Returns:
        bool: True if the environmental conditions trigger the initiator, False otherwise.
    """
    if not (0 <= initiator.signal_id < env.num_signals):
        return False

    conc = float(env.signal_layers[initiator.signal_id, plant.x, plant.y])
    mode = initiator.response_curve

    if mode == "step":
        return conc >= initiator.min_concentration
    if mode == "hill":
        kd = initiator.half_saturation
        n = initiator.hill_cooperativity
        if conc > 0.0:
            cn = conc**n
            priming_factor = cn / (kd**n + cn)
            return bool(priming_factor >= 0.05)
        return False
    if mode == "logarithmic":
        return conc >= initiator.min_concentration

    return False


def _evaluate_initiator(
    trig: CompiledTrigger,
    plant: PlantComponent,
    env: GridEnvironment,
    swarm_population_by_cell_species: SwarmPopulationIndex | dict[tuple[int, int, int], int],
) -> bool:
    """Evaluates a trigger's initiator for a specific plant.

    Args:
        trig: The compiled trigger schema containing initiator configurations.
        plant: The plant entity component.
        env: The current state of the simulation environment.
        swarm_population_by_cell_species: The index of swarm populations mapped by location and species.

    Returns:
        bool: True if the trigger's conditions are met, False otherwise.
    """
    if isinstance(trig.schema.initiator, HerbivoreAttackInitiator):
        return (
            swarm_population_by_cell_species.get((plant.x, plant.y, trig.schema.initiator.herbivore_species_id), 0)
            >= trig.schema.initiator.min_herbivore_population
        )

    if isinstance(trig.schema.initiator, EnvironmentalSignalInitiator):
        return _evaluate_environmental_signal(trig.schema.initiator, plant, env)

    return False
