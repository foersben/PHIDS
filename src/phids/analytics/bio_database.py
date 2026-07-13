"""Biological database component for matching traits and parameters.

Provides Pydantic models for flora and herbivore profiles, and the main
BioDatabase service for Mode A matching and Mode B bounds query logic.
"""

import json
import math
from pathlib import Path

from pydantic import BaseModel


class FloraProfile(BaseModel):
    """Profile parameters representing a specific flora species.

    Attributes:
        growth_rate: Photosynthetic growth rate percentage per tick.
        max_energy: Maximum physiological energy capacity.
        survival_threshold: Energy reserve threshold below which the plant dies.
        seed_cost: Caloric cost to reproduce/drop a seed.
        seed_dispersion_radius: Maximum radius for seed dispersal.

    """

    growth_rate: float
    max_energy: float
    survival_threshold: float
    seed_cost: float
    seed_dispersion_radius: float


class HerbivoreProfile(BaseModel):
    """Profile parameters representing a specific herbivore species.

    Attributes:
        metabolism_upkeep: Tick-by-tick base metabolic energy cost.
        consumption_rate: Feeding consumption rate per tick.
        mitosis_threshold: Energy threshold required to undergo mitosis.
        split_ratio: Energy and population allocation ratio on split.

    """

    metabolism_upkeep: float
    consumption_rate: float
    mitosis_threshold: float
    split_ratio: float


class BioDatabaseModel(BaseModel):
    """Container model matching the JSON structure of the biological database.

    Attributes:
        flora: Dictionary mapping flora species names to their profiles.
        herbivores: Dictionary mapping herbivore species names to their profiles.

    """

    flora: dict[str, FloraProfile]
    herbivores: dict[str, HerbivoreProfile]


class BioDatabase:
    """Provides Generative (Mode A) and Constrained (Mode B) database queries.

    Attributes:
        data: The validated BioDatabaseModel payload loaded from JSON.

    """

    def __init__(self, db_path: str = "src/phids/analytics/bio_database.json"):
        """Initialise the bio database from the given JSON file path.

        Args:
            db_path: Path to the bio_database.json file.

        """
        with open(Path(db_path)) as f:
            self.data = BioDatabaseModel(**json.load(f))

    def _euclidean_distance(self, v1: list[float], v2: list[float]) -> float:
        """Calculate the Euclidean distance between two vectors.

        Args:
            v1: First vector.
            v2: Second vector.

        Returns:
            The float distance value.

        """
        return math.sqrt(sum((a - b) ** 2 for a, b in zip(v1, v2, strict=True)))

    def mode_a_match_flora(self, target_vector: list[float]) -> str:
        """Matches a target vector to the closest database flora species name.

        Args:
            target_vector: A list of floats containing [growth_rate, max_energy, seed_cost].

        Returns:
            The name of the closest flora species found in the database.

        """
        best_match = None
        min_dist = float("inf")
        for name, profile in self.data.flora.items():
            db_vector = [profile.growth_rate, profile.max_energy, profile.seed_cost]
            # In production, normalize these vectors to prevent max_energy from dominating
            dist = self._euclidean_distance(target_vector, db_vector)
            if dist < min_dist:
                min_dist = dist
                best_match = name
        return best_match if best_match is not None else ""

    def mode_a_match_herbivore(self, target_vector: list[float]) -> str:
        """Matches a target vector to the closest database herbivore species name.

        Args:
            target_vector: A list of floats containing [metabolism_upkeep, mitosis_threshold].

        Returns:
            The name of the closest herbivore species found in the database.

        """
        best_match = None
        min_dist = float("inf")
        for name, profile in self.data.herbivores.items():
            db_vector = [profile.metabolism_upkeep, profile.mitosis_threshold]
            dist = self._euclidean_distance(target_vector, db_vector)
            if dist < min_dist:
                min_dist = dist
                best_match = name
        return best_match if best_match is not None else ""

    def mode_b_get_bounds_flora(self, species_name: str) -> dict[str, tuple[float, float]]:
        """Returns ±20% mutation bounds for a specific flora species.

        Args:
            species_name: Name of the flora species to lookup.

        Returns:
            A dictionary mapping trait keys to (min_bound, max_bound) tuples.

        Raises:
            ValueError: If the species_name is not found in the database.

        """
        if species_name not in self.data.flora:
            raise ValueError(f"Species {species_name} not found.")
        profile = self.data.flora[species_name].model_dump()
        return {k: (max(1e-4, v * 0.8), v * 1.2) for k, v in profile.items()}

    def mode_b_get_bounds_herbivore(self, species_name: str) -> dict[str, tuple[float, float]]:
        """Returns ±20% mutation bounds for a specific herbivore species.

        Args:
            species_name: Name of the herbivore species to lookup.

        Returns:
            A dictionary mapping trait keys to (min_bound, max_bound) tuples.

        Raises:
            ValueError: If the species_name is not found in the database.

        """
        if species_name not in self.data.herbivores:
            raise ValueError(f"Species {species_name} not found.")
        profile = self.data.herbivores[species_name].model_dump()
        return {k: (max(1e-4, v * 0.8), v * 1.2) for k, v in profile.items()}
