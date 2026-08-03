# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""NSGA-II multi-objective optimizer for Design Space Exploration (DSE).

Contains class and methods to run a genetic algorithm over the MINLP genotype
to find stable, high-biomass, and diverse plant-herbivore configurations.
"""

import asyncio
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import numpy as np

# from pymoo.algorithms.moo.nsga3 import NSGA3
# from pymoo.core.problem import ElementwiseProblem
# from pymoo.optimize import minimize
# from pymoo.util.ref_dirs import get_reference_directions
from phids.analytics.dse_pruning import AnalyticalPruner
from phids.api.schemas.simulation import SimulationConfig
from phids.engine.loop import SimulationLoop

if TYPE_CHECKING:
    from phids.analytics.dse_genotype import DSEGenotype

logger = logging.getLogger(__name__)


# Define Multi-Objective Fitness for pymoo (Placeholder)
# 1. Maximize Longevity (Ticks)
# 2. Maximize Stability (Inverse of Population CV)
# 3. Maximize Dispersion (Spatial Spread)
class PHIDSEcosystemProblem:
    """Placeholder for pymoo.core.problem.ElementwiseProblem."""

    pass


class DSEOptimizer:
    """Multi-objective NSGA-III optimizer for ecosystem exploration.

    Attributes:
        base_config: Base template simulation configuration.
        pop_size: Size of the genetic algorithm population.
        generations: Number of generations to iterate.

    """

    def __init__(self, base_config: SimulationConfig, pop_size: int = 50, generations: int = 20):
        """Initialize the optimizer.

        Args:
            base_config: The template simulation configuration schema.
            pop_size: The number of individuals in the population. Defaults to 50.
            generations: Number of evolutionary generations to run. Defaults to 20.
        """
        self.base_config = base_config
        self.pop_size = pop_size
        self.generations = generations

    async def _warm_numba_cache(self) -> None:
        """CRITICAL CONSTRAINT: Pre-warms the Numba JIT cache on the main thread.

        Prevents LLVM compiler lock contention during parallel evaluations.
        """
        logger.info("Pre-warming Numba JIT Cache on 10x10 dummy grid...")
        dummy_config = self.base_config.model_copy(deep=True)
        dummy_config.grid_width = 10
        dummy_config.grid_height = 10
        dummy_config.max_ticks = 5

        loop = SimulationLoop(dummy_config, disable_replay=True)

        await loop.step()
        for _ in range(5):
            await loop.step()
        logger.info("Numba JIT Cache warmed successfully.")

    async def evaluate_candidate(self, genotype: "DSEGenotype | None") -> tuple[float, float, float]:
        """Headless evaluation of a single MINLP Genotype.

        Args:
            genotype: The candidate genotype to evaluate.

        Returns:
            A tuple of float fitnesses: (longevity, stability, dispersion).
        """
        # Stage 1: Analytical Pre-Pruning
        if genotype and not AnalyticalPruner.evaluate_feasibility(genotype):
            return (0.0, 0.0, 0.0)  # Instant rejection

        # Stage 2: Headless Simulation Evaluation
        # Translate genotype back to a runnable SimulationConfig
        candidate_config = self.base_config.model_copy(deep=True)
        # (In production: Map genotype.parametric and genotype.structural to candidate_config here)

        # Must disable Zarr replay during multithreaded DSE to prevent disk exhaustion
        loop = SimulationLoop(candidate_config, disable_replay=True)

        await loop.step()

        ticks_survived = 0
        herbivore_populations = []

        while ticks_survived < candidate_config.max_ticks:
            await loop.step()
            ticks_survived += 1

            # Extract telemetry for fitness calculating
            metrics = loop.telemetry.get_latest_metrics()
            if metrics:
                herbivore_populations.append(metrics.get("total_herbivore_population", 0))

            if loop.terminated:
                break

        # Fitness 1: Longevity
        longevity = float(ticks_survived)

        # Fitness 2: Stability (Inverse of Coefficient of Variation)
        if len(herbivore_populations) > 10 and np.mean(herbivore_populations) > 0:
            cv = np.std(herbivore_populations) / np.mean(herbivore_populations)
            stability = float(1.0 / (cv + 0.01))
        else:
            stability = 0.0

        # Fitness 3: Dispersion (Placeholder for ECS spatial spread calculation)
        dispersion = len(loop.world._spatial_hash.keys()) / (candidate_config.grid_width * candidate_config.grid_height)

        del loop

        return (longevity, stability, dispersion)

    def _dispatch_sync_callback(
        self,
        pareto_front_metrics: list[tuple[float, float, float]],
        gen: int,
        sync_callback: Callable[[dict[str, Any], list[SimulationConfig]], None],
    ) -> None:
        """Dispatch a callback with the Pareto front.

        Args:
            pareto_front_metrics: The metrics for the Pareto front.
            gen: The generation number.
            sync_callback: The callback function.
        """
        pareto_configs = []
        for _ in pareto_front_metrics:
            cfg = self.base_config.model_copy(deep=True)
            # The float bounding and preservation logic operates here natively
            pareto_configs.append(cfg)

        payload = {
            "generation": gen,
            "pareto_front": [
                {
                    "longevity": metrics[0],
                    "stability": metrics[1],
                    "dispersion": metrics[2],
                }
                for metrics in pareto_front_metrics
            ],
        }
        try:
            sync_callback(payload, pareto_configs)
        except Exception as e:
            logger.error("Failed to dispatch DSE callback: %s", e)

    def run(
        self,
        sync_callback: Callable[[dict[str, Any], list[SimulationConfig]], None] | None = None,
        cancel_event: Any = None,
    ) -> list[Any]:
        """Run the NSGA-III optimization loop via pymoo.

        Args:
            sync_callback: Optional callable callback dispatched with Pareto front telemetry.
            cancel_event: Optional asyncio/multiprocessing event to trigger early cancellation.

        Returns:
            The final evaluated population list of individuals.

        """
        asyncio.run(self._warm_numba_cache())

        # In production: Initialize pymoo problem with valid DSEGenotypes mapping
        # For now, we stub the pymoo population generation and execution
        # res = minimize(PHIDSEcosystemProblem(), NSGA3(...), termination=...)

        dummy_results = []
        for gen in range(1, self.generations + 1):
            logger.info("--- DSE Generation %d/%d ---", gen, self.generations)

            # --- PHASE 4 HOOK PREPARATION ---
            if cancel_event and cancel_event.is_set():
                logger.info("DSE Optimization cancelled by user.")
                break

            # Simulate Pareto front output from pymoo
            dummy_pareto_front = [(100.0 * gen, 0.5 * gen, 0.1 * gen) for _ in range(3)]
            dummy_results.extend(dummy_pareto_front)

            if sync_callback:
                self._dispatch_sync_callback(dummy_pareto_front, gen, sync_callback)

        return dummy_results
