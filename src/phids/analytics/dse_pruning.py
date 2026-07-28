# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Analytical pre-pruning system for Design Space Exploration (DSE).

Contains validators to filter out structurally and thermodynamically unviable
genotypes before running computationally expensive simulations.
"""

import logging
from typing import Any

from phids.analytics.dse_genotype import DSEGenotype

logger = logging.getLogger(__name__)


class AnalyticalPruner:
    """Executes Stage 1 of the DSE: Pre-Exploration Pruning via Analytical Bounds.

    Eliminates infeasible MINLP configurations instantly to save CPU cycles.
    """

    @staticmethod
    def _check_diet_feasibility(genotype: DSEGenotype, herbivore_ids: list[int], flora_ids: list[int]) -> bool:
        """Check if the diet is feasible.

        Args:
            genotype: The DSE genotype.
            herbivore_ids: The list of herbivore indices.
            flora_ids: The list of flora indices.

        Returns:
            True if no herbivore has an empty diet, otherwise False.
        """
        for h_idx in herbivore_ids:
            edible_plants = [f_idx for f_idx in flora_ids if genotype.structural.diet_matrix[h_idx][f_idx]]
            if not edible_plants:
                logger.debug("Pruned: Herbivore %d has no edible plants in diet matrix.", h_idx)
                return False
        return True

    @staticmethod
    def _check_caloric_conservation(genotype: DSEGenotype, herbivore_ids: list[int], flora_ids: list[int]) -> bool:
        """Check if caloric conservation is feasible.

        Args:
            genotype: The DSE genotype.
            herbivore_ids: The list of herbivore indices.
            flora_ids: The list of flora indices.

        Returns:
            True if caloric conservation is feasible, False otherwise.
        """
        for h_idx in herbivore_ids:
            edible_plants = [f_idx for f_idx in flora_ids if genotype.structural.diet_matrix[h_idx][f_idx]]
            h_name = list(genotype.parametric.herbivore_traits.keys())[h_idx]
            herbivore = genotype.parametric.herbivore_traits[h_name]

            max_available_calories = 0.0
            for f_idx in edible_plants:
                f_name = list(genotype.parametric.flora_traits.keys())[f_idx]
                flora = genotype.parametric.flora_traits[f_name]
                available_energy = max(0.0, flora.max_energy - flora.survival_threshold)
                max_bite = min(available_energy, herbivore.consumption_rate)
                if max_bite > max_available_calories:
                    max_available_calories = max_bite

            if max_available_calories < herbivore.metabolism_upkeep:
                logger.debug("Pruned: Caloric deficit for %s. Upkeep exceeds max available intake.", h_name)
                return False
        return True

    @staticmethod
    def _calculate_total_flora_tiles(f_placement: Any, grid_area: float) -> float:
        """Calculate total flora tiles.

        Args:
            f_placement: The flora placement.
            grid_area: The grid area.

        Returns:
            The total flora tiles.
        """
        if f_placement.type == "uniform":
            return float(grid_area * f_placement.density)
        elif f_placement.type == "clustered":
            return float(min(grid_area, f_placement.cluster_count * 9.0))
        else:
            return float(min(grid_area, f_placement.band_count * 40.0))

    @staticmethod
    def _calculate_total_herbivores(h_placement: Any, grid_area: float) -> float:
        """Calculate total herbivores.

        Args:
            h_placement: The herbivore placement.
            grid_area: The grid area.

        Returns:
            The total herbivores.
        """
        if h_placement.type == "uniform":
            return float(grid_area * h_placement.density)
        elif h_placement.type == "clustered":
            return float(min(grid_area, h_placement.cluster_count * 5.0))
        else:
            return float(min(grid_area, h_placement.band_count * 10.0))

    @staticmethod
    def _check_global_thermodynamics(genotype: DSEGenotype, herbivore_ids: list[int], flora_ids: list[int]) -> bool:
        """Check global thermodynamics.

        Args:
            genotype: The DSE genotype.
            herbivore_ids: The list of herbivore indices.
            flora_ids: The list of flora indices.

        Returns:
            True if global thermodynamics is feasible, False otherwise.
        """
        grid_area = 1600.0

        total_flora_tiles = AnalyticalPruner._calculate_total_flora_tiles(
            genotype.structural.flora_placement, grid_area
        )
        num_flora_species = max(1, len(flora_ids))
        n_max_tiles_per_flora = total_flora_tiles / num_flora_species

        total_herbivores = AnalyticalPruner._calculate_total_herbivores(
            genotype.structural.herbivore_placement, grid_area
        )
        num_herbivore_species = max(1, len(herbivore_ids))
        n_initial_per_herbivore = total_herbivores / num_herbivore_species

        total_primary_production = 0.0
        for _f_name, flora in genotype.parametric.flora_traits.items():
            yield_energy = max(0.0, flora.max_energy - flora.survival_threshold)
            total_primary_production += yield_energy * (flora.growth_rate / 100.0) * n_max_tiles_per_flora

        total_metabolism = 0.0
        for _h_name, herbivore in genotype.parametric.herbivore_traits.items():
            total_metabolism += herbivore.metabolism_upkeep * n_initial_per_herbivore

        if total_primary_production <= total_metabolism and total_metabolism > 0:
            logger.debug("Pruned: Global thermodynamic bounds violated.")
            return False
        return True

    @staticmethod
    def _check_flora_biological_validity(genotype: DSEGenotype) -> bool:
        """Check flora biological validity.

        Args:
            genotype: The DSE genotype.

        Returns:
            True if flora biological validity is feasible, False otherwise.
        """
        for f_name, flora in genotype.parametric.flora_traits.items():
            if flora.seed_cost >= (flora.max_energy - flora.survival_threshold):
                logger.debug("Pruned: Flora %s seed cost causes immediate self-termination.", f_name)
                return False
        return True

    @staticmethod
    def evaluate_feasibility(genotype: DSEGenotype) -> bool:
        """Returns True if the genotype is mathematically viable, False if doomed.

        Performs:
        1. Structural diet checks (ensures no herbivore starves by design).
        2. Individual caloric conservation checks.
        3. Global thermodynamic bounds checks.
        4. Flora self-termination (seed cost vs max yield) checks.

        Args:
            genotype: The candidate DSEGenotype to evaluate.

        Returns:
            True if the genotype is mathematically viable, False otherwise.
        """
        herbivore_ids = list(range(len(genotype.parametric.herbivore_traits)))
        flora_ids = list(range(len(genotype.parametric.flora_traits)))

        if not AnalyticalPruner._check_diet_feasibility(genotype, herbivore_ids, flora_ids):
            return False

        if not AnalyticalPruner._check_caloric_conservation(genotype, herbivore_ids, flora_ids):
            return False

        if not AnalyticalPruner._check_global_thermodynamics(genotype, herbivore_ids, flora_ids):
            return False

        if not AnalyticalPruner._check_flora_biological_validity(genotype):
            return False

        return True
