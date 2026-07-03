import json
import math
from pathlib import Path

from pydantic import BaseModel


class FloraProfile(BaseModel):
    """Profile parameters for flora species."""

    growth_rate: float
    max_energy: float
    survival_threshold: float
    seed_cost: float
    seed_dispersion_radius: float


class HerbivoreProfile(BaseModel):
    """Profile parameters for herbivore species."""

    metabolism_upkeep: float
    consumption_rate: float
    mitosis_threshold: float
    split_ratio: float


class BioDatabaseModel(BaseModel):
    """JSON structure for the biological database."""

    flora: dict[str, FloraProfile]
    herbivores: dict[str, HerbivoreProfile]


class BioDatabase:
    """Provides Generative (Mode A) and Constrained (Mode B) data access."""

    def __init__(self, db_path: str = "src/phids/analytics/bio_database.json"):
        """Initialise the bio database from the given JSON file path."""
        with open(Path(db_path)) as f:
            self.data = BioDatabaseModel(**json.load(f))

    def _euclidean_distance(self, v1: list[float], v2: list[float]) -> float:
        return math.sqrt(sum((a - b) ** 2 for a, b in zip(v1, v2, strict=True)))

    def mode_a_match_flora(self, target_vector: list[float]) -> str:
        """Matches [growth_rate, max_energy, seed_cost] to closest Flora."""
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
        """Matches [metabolism_upkeep, mitosis_threshold] to closest Herbivore."""
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
        """Returns ±20% bounds for specific flora."""
        if species_name not in self.data.flora:
            raise ValueError(f"Species {species_name} not found.")
        profile = self.data.flora[species_name].model_dump()
        return {k: (max(1e-4, v * 0.8), v * 1.2) for k, v in profile.items()}

    def mode_b_get_bounds_herbivore(self, species_name: str) -> dict[str, tuple[float, float]]:
        """Returns ±20% bounds for specific herbivore."""
        if species_name not in self.data.herbivores:
            raise ValueError(f"Species {species_name} not found.")
        profile = self.data.herbivores[species_name].model_dump()
        return {k: (max(1e-4, v * 0.8), v * 1.2) for k, v in profile.items()}
