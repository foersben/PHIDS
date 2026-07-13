"""Analytical pre-pruning system for Design Space Exploration (DSE).

Contains validators to filter out structurally and thermodynamically unviable
genotypes before running computationally expensive simulations.
"""

import logging

from phids.analytics.dse_genotype import DSEGenotype

logger = logging.getLogger(__name__)


class AnalyticalPruner:
    """Executes Stage 1 of the DSE: Pre-Exploration Pruning via Analytical Bounds.

    Eliminates infeasible MINLP configurations instantly to save CPU cycles.
    """

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

        # Check 1: Structural Diet Feasibility (No starvation by design)
        for h_idx in herbivore_ids:
            edible_plants = [f_idx for f_idx in flora_ids if genotype.structural.diet_matrix[h_idx][f_idx]]
            if not edible_plants:
                logger.debug("Pruned: Herbivore %d has no edible plants in diet matrix.", h_idx)
                return False

        # Check 2a: Individual Caloric Mass Conservation
        # A herbivore's upkeep MUST be lower than the max energy it can consume in a tick
        for h_idx in herbivore_ids:
            edible_plants = [f_idx for f_idx in flora_ids if genotype.structural.diet_matrix[h_idx][f_idx]]
            h_name = list(genotype.parametric.herbivore_traits.keys())[h_idx]
            herbivore = genotype.parametric.herbivore_traits[h_name]

            # Find the highest calorie density among edible plants
            max_available_calories = 0.0
            for f_idx in edible_plants:
                f_name = list(genotype.parametric.flora_traits.keys())[f_idx]
                flora = genotype.parametric.flora_traits[f_name]
                # Maximum bite size is constrained by the plant's available yield (max_energy - survival_threshold)
                # and the herbivore's maximum consumption rate
                available_energy = max(0.0, flora.max_energy - flora.survival_threshold)
                max_bite = min(available_energy, herbivore.consumption_rate)
                if max_bite > max_available_calories:
                    max_available_calories = max_bite

            # If the best possible bite doesn't even cover base metabolism, inevitable extinction
            if max_available_calories < herbivore.metabolism_upkeep:
                logger.debug("Pruned: Caloric deficit for %s. Upkeep exceeds max available intake.", h_name)
                return False

        # Check 2b: Global Thermodynamic Bound
        # Maximum total caloric production of all plants per tick must exceed total initial herbivore metabolism.
        # Estimate N_max_tiles per plant species and initial population per herbivore based on placement.
        # Assuming a standard 40x40 grid bounds for DSE evaluation.
        grid_area = 1600.0

        f_placement = genotype.structural.flora_placement
        if f_placement.type == "uniform":
            total_flora_tiles = grid_area * f_placement.density
        elif f_placement.type == "clustered":
            total_flora_tiles = min(grid_area, f_placement.cluster_count * 9.0)  # Assume ~9 tiles per cluster
        else:  # banded
            total_flora_tiles = min(grid_area, f_placement.band_count * 40.0)  # Assume 40 length band

        num_flora_species = max(1, len(flora_ids))
        n_max_tiles_per_flora = total_flora_tiles / num_flora_species

        h_placement = genotype.structural.herbivore_placement
        if h_placement.type == "uniform":
            total_herbivores = grid_area * h_placement.density
        elif h_placement.type == "clustered":
            total_herbivores = min(grid_area, h_placement.cluster_count * 5.0)
        else:  # banded
            total_herbivores = min(grid_area, h_placement.band_count * 10.0)

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

        # Check 3: Flora Biological Validity
        for f_name, flora in genotype.parametric.flora_traits.items():
            if flora.seed_cost >= (flora.max_energy - flora.survival_threshold):
                logger.debug("Pruned: Flora %s seed cost causes immediate self-termination.", f_name)
                return False

        return True
