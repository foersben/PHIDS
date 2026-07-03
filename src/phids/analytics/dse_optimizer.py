import logging
import random
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING

import numpy as np
from deap import base, creator, tools  # type: ignore[import-untyped]

from phids.analytics.dse_pruning import AnalyticalPruner
from phids.api.schemas import SimulationConfig
from phids.engine.loop import SimulationLoop

if TYPE_CHECKING:
    from phids.analytics.dse_genotype import DSEGenotype

logger = logging.getLogger(__name__)

# Define Multi-Objective Fitness:
# 1. Maximize Longevity (Ticks)
# 2. Maximize Stability (Inverse of Population CV)
# 3. Maximize Dispersion (Spatial Spread)
creator.create("FitnessMax", base.Fitness, weights=(1.0, 1.0, 1.0))
creator.create("Individual", list, fitness=creator.FitnessMax, genotype=None)


class DSEOptimizer:
    """Multi-objective NSGA-II optimizer for ecosystem exploration."""

    def __init__(self, base_config: SimulationConfig, pop_size: int = 50, generations: int = 20):
        """Initialize the optimizer."""
        self.base_config = base_config
        self.pop_size = pop_size
        self.generations = generations
        self.toolbox = base.Toolbox()
        self._setup_deap()

    async def _warm_numba_cache(self) -> None:
        """CRITICAL CONSTRAINT: Pre-warms the Numba JIT cache on the main thread.

        Prevents LLVM compiler lock contention during parallel evaluations.
        """
        logger.info("Pre-warming Numba JIT Cache on 10x10 dummy grid...")
        dummy_config = self.base_config.model_copy(deep=True)
        dummy_config.grid_width = 10
        dummy_config.grid_height = 10
        dummy_config.max_ticks = 5

        loop = SimulationLoop(dummy_config)

        await loop.step()
        for _ in range(5):
            await loop.step()
        logger.info("Numba JIT Cache warmed successfully.")

    def _setup_deap(self) -> None:
        # In a full implementation, you would register custom MINLP crossover/mutation here
        # that knows how to splice the DSEGenotype properly.
        self.toolbox.register("evaluate", self.evaluate_candidate_sync)
        self.toolbox.register("mate", tools.cxSimulatedBinaryBounded, eta=20.0, low=1e-4, up=1.0)
        self.toolbox.register("mutate", tools.mutPolynomialBounded, eta=20.0, low=1e-4, up=1.0, indpb=1.0 / 10.0)
        self.toolbox.register("select", tools.selNSGA2)

    def evaluate_candidate_sync(self, individual: "creator.Individual") -> tuple[float, float, float]:
        """Synchronous wrapper for DEAP compatibility."""
        import asyncio

        return asyncio.run(self.evaluate_candidate(individual))

    async def evaluate_candidate(self, individual: "creator.Individual") -> tuple[float, float, float]:
        """Headless evaluation of a single MINLP Genotype."""
        genotype: DSEGenotype | None = individual.genotype

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

    def run(self) -> list["creator.Individual"]:
        """Run the NSGA-II optimization."""
        import asyncio

        asyncio.run(self._warm_numba_cache())

        # In production: Initialize population with valid DSEGenotypes mapping
        # For now, we stub the DEAP population generation
        pop = [creator.Individual([random.random() for _ in range(10)]) for _ in range(self.pop_size)]

        # We need a proper stub genotype for evaluate_candidate
        # but model_construct may fail on nested schemas. Let's create a minimal valid base config Genotype instead.
        for ind in pop:
            ind.genotype = None  # The evaluator handles None by evaluating the base_config directly

        # Evaluate the initial population
        invalid_ind = [ind for ind in pop if not ind.fitness.valid]
        with ThreadPoolExecutor(max_workers=4) as executor:
            fitnesses = list(executor.map(self.toolbox.evaluate, invalid_ind))

        for ind, fit in zip(invalid_ind, fitnesses, strict=False):
            ind.fitness.values = fit

        pop = self.toolbox.select(pop, len(pop))

        # The NSGA-II Loop
        for gen in range(1, self.generations + 1):
            logger.info("--- DSE Generation %d/%d ---", gen, self.generations)

            offspring = tools.selTournamentDCD(pop, len(pop))
            offspring = [self.toolbox.clone(ind) for ind in offspring]

            for ind1, ind2 in zip(offspring[::2], offspring[1::2], strict=False):
                if random.random() <= 0.9:
                    self.toolbox.mate(ind1, ind2)
                self.toolbox.mutate(ind1)
                self.toolbox.mutate(ind2)
                del ind1.fitness.values, ind2.fitness.values

            # In a full implementation, we must re-sync the continuous DEAP float lists
            # back to the explicit MINLP DSEGenotype here before evaluation.

            invalid_ind = [ind for ind in offspring if not ind.fitness.valid]
            with ThreadPoolExecutor(max_workers=4) as executor:
                fitnesses = list(executor.map(self.toolbox.evaluate, invalid_ind))

            for ind, fit in zip(invalid_ind, fitnesses, strict=False):
                ind.fitness.values = fit

            # Select the next generation population
            pop = self.toolbox.select(pop + offspring, self.pop_size)

            # --- PHASE 4 HOOK PREPARATION ---
            # Future location of WebSocket Pareto Front broadcast
            # yield {"generation": gen, "pareto_front": [ind.fitness.values for ind in pop[:5]]}

        return list(pop)
