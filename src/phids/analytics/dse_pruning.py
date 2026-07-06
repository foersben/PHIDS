import logging

from phids.analytics.dse_genotype import DSEGenotype

logger = logging.getLogger(__name__)


class AnalyticalPruner:
    """Executes Stage 1 of the DSE: Pre-Exploration Pruning via Analytical Bounds.

    Eliminates infeasible MINLP configurations instantly to save CPU cycles.
    """

    @staticmethod
    def evaluate_feasibility(genotype: DSEGenotype) -> bool:
        """Returns True if the genotype is mathematically viable, False if doomed."""
        # Check 1: Structural Diet Feasibility (No starvation by design)
        # Assuming species IDs map to the indices of the dicts and matrices
        herbivore_ids = list(range(len(genotype.parametric.herbivore_traits)))
        flora_ids = list(range(len(genotype.parametric.flora_traits)))

        for h_idx in herbivore_ids:
            edible_plants = [f_idx for f_idx in flora_ids if genotype.structural.diet_matrix[h_idx][f_idx]]
            if not edible_plants:
                logger.debug("Pruned: Herbivore %d has no edible plants in diet matrix.", h_idx)
                return False

            # Check 2: Caloric Mass Conservation
            # A herbivore's upkeep MUST be lower than the max energy it can consume in a tick
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

        # Check 3: Flora Biological Validity
        for f_name, flora in genotype.parametric.flora_traits.items():
            if flora.seed_cost >= (flora.max_energy - flora.survival_threshold):
                logger.debug("Pruned: Flora %s seed cost causes immediate self-termination.", f_name)
                return False

        return True
