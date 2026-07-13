# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Automated hyperparameter tuning pipeline using Differential Evolution.

This module provides the :class:`TrophicOptimizer` to autonomously search for
stable Lotka-Volterra parameters over complex multi-species scenarios.
"""

from __future__ import annotations

import concurrent.futures
import json
import logging
from typing import Any, cast

import numpy as np
from scipy.optimize import differential_evolution  # type: ignore

from phids.engine.batch import _run_and_save

logger = logging.getLogger(__name__)


class TrophicOptimizer:
    """Hyperparameter tuner utilizing Scipy's Differential Evolution.

    Mutates a given scenario blueprint to find a parameter regime that maximizes
    ecosystem survival over a large number of ticks, using population CV as a
    secondary stability metric.

    Attributes:
        blueprint: The baseline scenario configuration.
        runs_per_eval: Number of concurrent stochastic runs per evaluation.
        max_ticks: Target simulation duration per run.
        bounds: List of min/max boundary value tuples for each parameter.
        param_mapping: Mapping of float indices to blueprint keys.

    """

    def __init__(
        self,
        blueprint: dict[str, Any],
        runs_per_eval: int = 20,
        max_ticks: int = 2500,
    ) -> None:
        """Initialize the optimizer.

        Args:
            blueprint: The baseline scenario configuration.
            runs_per_eval: Number of concurrent stochastic runs per evaluation.
            max_ticks: Target simulation duration per run.

        """
        self.blueprint = blueprint
        self.runs_per_eval = runs_per_eval
        self.max_ticks = max_ticks

        self.bounds: list[tuple[float, float]] = []
        self.param_mapping: list[tuple[str, int, str]] = []

        self._setup_bounds()

    def _setup_bounds(self) -> None:
        """Extract tunable parameters from the blueprint and set numerical bounds."""
        for i, _flora in enumerate(self.blueprint.get("flora_species", [])):
            # Growth rate (g_j)
            self.bounds.append((1.0, 15.0))
            self.param_mapping.append(("flora_species", i, "growth_rate"))

            # Seed min distance
            self.bounds.append((0.5, 3.0))
            self.param_mapping.append(("flora_species", i, "seed_min_dist"))

            # Seed max distance
            self.bounds.append((3.1, 10.0))
            self.param_mapping.append(("flora_species", i, "seed_max_dist"))

        for i, _herb in enumerate(self.blueprint.get("herbivore_species", [])):
            # Metabolic maintenance (m_i)
            self.bounds.append((0.01, 1.0))
            self.param_mapping.append(("herbivore_species", i, "energy_upkeep_per_individual"))

            # Reproduction cost (c_i) mapped to reproduction_energy_divisor
            self.bounds.append((0.1, 5.0))
            self.param_mapping.append(("herbivore_species", i, "reproduction_energy_divisor"))

    def _apply_params(self, x: np.ndarray) -> dict[str, Any]:
        """Inject an array of values back into a deepcopy of the blueprint.

        Args:
            x: A NumPy array containing the values to apply.

        Returns:
            The modified scenario configuration blueprint dictionary.

        """
        config = cast("dict[str, Any]", json.loads(json.dumps(self.blueprint)))
        for val, (category, idx, key) in zip(x, self.param_mapping, strict=False):
            config[category][idx][key] = float(val)
        return config

    def _evaluate(self, x: np.ndarray) -> float:
        """Evaluate fitness of a parameter vector over N concurrent simulations.

        Args:
            x: A NumPy array containing candidate parameter values.

        Returns:
            The calculated float fitness/stability score (lower is better).

        """
        config = self._apply_params(x)

        # Disable logging overhead during mass evaluation
        # The empty string disables Zarr replay persistence in the worker
        args_list = [(config, self.max_ticks, seed, "tune", i, "") for i, seed in enumerate(range(self.runs_per_eval))]

        results = []
        # Use ProcessPoolExecutor to max out IPC throughput
        with concurrent.futures.ProcessPoolExecutor() as executor:
            for res in executor.map(_run_and_save, args_list):
                results.append(res)

        survived = 0
        cvs: list[float] = []

        for run_telemetry in results:
            if not run_telemetry:
                continue

            last_tick = int(str(run_telemetry[-1].get("tick", 0)))
            # If the run lasted at least max_ticks - 1, it survived
            if last_tick >= self.max_ticks - 1:
                survived += 1

                # Calculate stability for this successful run
                flora_pop = [float(str(r.get("flora_population", 0.0))) for r in run_telemetry]
                herb_pop = [float(str(r.get("herbivore_population", 0.0))) for r in run_telemetry]

                f_mean = float(np.mean(flora_pop))
                h_mean = float(np.mean(herb_pop))

                if f_mean > 0 and h_mean > 0:
                    f_cv = float(np.std(flora_pop)) / f_mean
                    h_cv = float(np.std(herb_pop)) / h_mean
                    cvs.append((f_cv + h_cv) / 2.0)
                else:
                    cvs.append(100.0)

        # Target 80% survival rate
        target_survived = int(self.runs_per_eval * 0.8)
        failure_penalty = max(0, target_survived - survived) * 1000.0

        if survived > 0 and cvs:
            avg_cv = sum(cvs) / len(cvs)
        else:
            avg_cv = 1000.0

        score = failure_penalty + avg_cv
        logger.info(
            "Genome Evaluation: survived=%d/%d, avg_cv=%.3f, fitness_score=%.3f",
            survived,
            self.runs_per_eval,
            avg_cv,
            score,
        )
        return score

    def optimize(self) -> dict[str, Any]:
        """Run the Differential Evolution optimization loop.

        Returns:
            The optimized configuration blueprint as a dictionary.

        """
        logger.info(
            "Starting stochastic optimization sweep with %d parameters and %d concurrent runs per eval",
            len(self.bounds),
            self.runs_per_eval,
        )

        # Note: popsize and maxiter can be aggressively tuned based on compute time.
        # Since each eval spawns 20 processes, keep the genetic population small.
        result = differential_evolution(
            self._evaluate,
            self.bounds,
            maxiter=15,
            popsize=3,
            disp=True,
            polish=False,
            workers=1,  # Keep main process single-threaded, concurrency is in the fitness function
        )

        logger.info("Optimization complete. Best fitness: %s", result.fun)
        best_config = self._apply_params(result.x)
        return best_config
