# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Genotype definitions representing the ecosystem design space.

Defines structural and parametric genes representing discrete choices and
continuous variables of the Mixed-Integer Non-Linear Programming (MINLP) genotype.
"""

from pydantic import BaseModel, field_validator

from phids.analytics.bio_database import FloraProfile, HerbivoreProfile
from phids.api.schemas.placement import PlacementStrategy


class StructuralGenes(BaseModel):
    """Discrete, structural choices of the ecosystem.

    Attributes:
        flora_placement: Spatial distribution strategy for flora.
        herbivore_placement: Spatial distribution strategy for herbivores.
        diet_matrix: A 16x16 boolean matrix defining diet compatibility.
        trigger_matrix: A 16x16 integer mapping of defensive trigger rules.

    """

    flora_placement: PlacementStrategy
    herbivore_placement: PlacementStrategy
    # 16x16 flattened or list-of-lists for Diet Compatibility
    diet_matrix: list[list[bool]]
    # 16x16 integer mapping of which plant triggers which toxin against which herbivore
    trigger_matrix: list[list[int]]

    @field_validator("diet_matrix", "trigger_matrix")
    @classmethod
    def validate_rule_of_16(cls, matrix: list[list[bool]] | list[list[int]]) -> list[list[bool]] | list[list[int]]:
        """Ensure matrix dimensions do not exceed 16x16.

        Args:
            matrix: The nested list matrix to validate.

        Returns:
            The validated matrix.

        Raises:
            ValueError: If the matrix violates the 16x16 dimension limits.

        """
        if len(matrix) > 16 or any(len(row) > 16 for row in matrix):
            raise ValueError("Matrix violates the Rule of 16 bounds.")
        return matrix


class ParametricGenes(BaseModel):
    """Continuous, tuneable float values representing biological traits.

    Attributes:
        flora_traits: Dictionary mapping flora species to their trait profiles.
        herbivore_traits: Dictionary mapping herbivore species to their trait profiles.

    """

    flora_traits: dict[str, FloraProfile]
    herbivore_traits: dict[str, HerbivoreProfile]


class DSEGenotype(BaseModel):
    """The complete Hierarchical MINLP Genotype representation.

    Attributes:
        scenario_name: Name of the candidate scenario.
        structural: The structural/discrete genes component.
        parametric: The parametric/continuous genes component.

    """

    scenario_name: str = "DSE_Candidate"
    structural: StructuralGenes
    parametric: ParametricGenes
