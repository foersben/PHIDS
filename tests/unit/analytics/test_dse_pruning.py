from phids.analytics.bio_database import FloraProfile, HerbivoreProfile
from phids.analytics.dse_genotype import DSEGenotype, ParametricGenes, StructuralGenes
from phids.analytics.dse_pruning import AnalyticalPruner
from phids.api.schemas import UniformPlacement


def _build_test_genotype(
    diet_matrix: list[list[bool]],
    herbivore_metabolism: float,
    herbivore_consumption: float,
    flora_max_energy: float,
    flora_survival_threshold: float,
    flora_seed_cost: float,
) -> DSEGenotype:
    flora_placement = UniformPlacement(density=0.1)
    herbivore_placement = UniformPlacement(density=0.1)
    structural = StructuralGenes(
        flora_placement=flora_placement,
        herbivore_placement=herbivore_placement,
        diet_matrix=diet_matrix,
        trigger_matrix=[[0]],
    )
    parametric = ParametricGenes(
        flora_traits={
            "TestFlora": FloraProfile(
                growth_rate=50.0,
                max_energy=flora_max_energy,
                survival_threshold=flora_survival_threshold,
                seed_cost=flora_seed_cost,
                seed_dispersion_radius=1.0,
            )
        },
        herbivore_traits={
            "TestHerbivore": HerbivoreProfile(
                metabolism_upkeep=herbivore_metabolism,
                consumption_rate=herbivore_consumption,
                mitosis_threshold=10.0,
                split_ratio=0.5,
            )
        },
    )
    return DSEGenotype(structural=structural, parametric=parametric)


def test_dse_pruning_feasible_genotype():
    """A mathematically sound ecosystem should pass."""
    genotype = _build_test_genotype(
        diet_matrix=[[True]],
        herbivore_metabolism=0.5,
        herbivore_consumption=2.0,
        flora_max_energy=20.0,
        flora_survival_threshold=2.0,
        flora_seed_cost=5.0,
    )
    assert AnalyticalPruner.evaluate_feasibility(genotype) is True


def test_dse_pruning_infeasible_no_edible_plants():
    """Herbivore with False in diet matrix for all plants should fail."""
    genotype = _build_test_genotype(
        diet_matrix=[[False]],
        herbivore_metabolism=0.5,
        herbivore_consumption=2.0,
        flora_max_energy=20.0,
        flora_survival_threshold=2.0,
        flora_seed_cost=5.0,
    )
    assert AnalyticalPruner.evaluate_feasibility(genotype) is False


def test_dse_pruning_infeasible_caloric_deficit():
    """Herbivore that burns more than it can physically eat should fail."""
    genotype = _build_test_genotype(
        diet_matrix=[[True]],
        herbivore_metabolism=5.0,  # Burns 5.0 per tick
        herbivore_consumption=2.0,  # Can only eat 2.0 per tick max
        flora_max_energy=20.0,
        flora_survival_threshold=2.0,
        flora_seed_cost=5.0,
    )
    assert AnalyticalPruner.evaluate_feasibility(genotype) is False


def test_dse_pruning_infeasible_flora_seed_cost():
    """Flora that dies upon reproducing should fail."""
    genotype = _build_test_genotype(
        diet_matrix=[[True]],
        herbivore_metabolism=0.5,
        herbivore_consumption=2.0,
        flora_max_energy=10.0,
        flora_survival_threshold=2.0,
        flora_seed_cost=15.0,  # Costs 15, but max energy is 10
    )
    assert AnalyticalPruner.evaluate_feasibility(genotype) is False
