from pydantic import BaseModel, field_validator

from phids.analytics.bio_database import FloraProfile, HerbivoreProfile
from phids.api.schemas import PlacementStrategy


class StructuralGenes(BaseModel):
    """Discrete, structural choices of the ecosystem."""

    flora_placement: PlacementStrategy
    herbivore_placement: PlacementStrategy
    # 16x16 flattened or list-of-lists for Diet Compatibility
    diet_matrix: list[list[bool]]
    # 16x16 integer mapping of which plant triggers which toxin against which herbivore
    trigger_matrix: list[list[int]]

    @field_validator("diet_matrix", "trigger_matrix")
    @classmethod
    def validate_rule_of_16(cls, matrix: list[list[bool]] | list[list[int]]) -> list[list[bool]] | list[list[int]]:
        """Ensure matrix bounds do not exceed 16x16."""
        if len(matrix) > 16 or any(len(row) > 16 for row in matrix):
            raise ValueError("Matrix violates the Rule of 16 bounds.")
        return matrix


class ParametricGenes(BaseModel):
    """Continuous, tuneable float values representing biological traits."""

    flora_traits: dict[str, FloraProfile]
    herbivore_traits: dict[str, HerbivoreProfile]


class DSEGenotype(BaseModel):
    """The complete Hierarchical MINLP Genotype."""

    scenario_name: str = "DSE_Candidate"
    structural: StructuralGenes
    parametric: ParametricGenes
