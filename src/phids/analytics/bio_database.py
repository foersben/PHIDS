# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

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
        passive_defenses: Morphological defense configuration.

    """

    growth_rate: float
    max_energy: float
    survival_threshold: float
    seed_cost: float
    seed_dispersion_radius: float
    passive_defenses: dict[str, float]


class HerbivoreProfile(BaseModel):
    """Profile parameters representing a specific herbivore species.

    Attributes:
        metabolism_upkeep: Tick-by-tick base metabolic energy cost.
        consumption_rate: Feeding consumption rate per tick.
        mitosis_threshold: Energy threshold required to undergo mitosis.
        split_ratio: Energy and population allocation ratio on split.
        resistances: Herbivore resistances to passive plant defenses.

    """

    metabolism_upkeep: float
    consumption_rate: float
    mitosis_threshold: float
    split_ratio: float
    resistances: dict[str, float]


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

    def __init__(self, db_path: str = "src/phids/analytics/bio_database.json", data: BioDatabaseModel | None = None):
        """Initialise the bio database from the given JSON file path or model.

        Args:
            db_path: Path to the bio_database.json file.
            data: Explicit BioDatabaseModel instance (overrides db_path).

        """
        if data is not None:
            self.data = data
        else:
            with open(Path(db_path)) as f:
                self.data = BioDatabaseModel(**json.load(f))

    @classmethod
    def from_duckdb(cls, db_path: str = "src/phids/analytics/bio_database.duckdb") -> "BioDatabase":
        """Initialise the bio database directly from the DuckDB file.

        Args:
            db_path: Path to the bio_database.duckdb file.

        Returns:
            A new BioDatabase instance populated from DuckDB.

        Raises:
            ImportError: If duckdb is not installed.
        """
        try:
            import duckdb
        except ImportError:
            raise ImportError("duckdb is required to use from_duckdb()") from None

        conn = duckdb.connect(db_path, read_only=True)

        flora_dict: dict[str, FloraProfile] = {}
        for row in conn.execute(
            "SELECT canonical_name, growth_rate, max_energy, survival_threshold, "
            "seed_cost, seed_dispersion_radius, mechanical_damage_per_bite, "
            "digestibility_modifier FROM flora_species"
        ).fetchall():
            name, growth, max_e, surv, seed_c, seed_r, mech, digest = row
            flora_dict[name] = FloraProfile(
                growth_rate=growth,
                max_energy=max_e,
                survival_threshold=surv,
                seed_cost=seed_c,
                seed_dispersion_radius=seed_r,
                passive_defenses={
                    "mechanical_damage_per_bite": mech,
                    "digestibility_modifier": digest,
                },
            )

        herb_dict: dict[str, HerbivoreProfile] = {}
        for row in conn.execute(
            "SELECT canonical_name, metabolism_upkeep, consumption_rate, "
            "mitosis_threshold, split_ratio, morphological_adaptation, "
            "chemical_neutralization, digestive_efficiency FROM herbivore_species"
        ).fetchall():
            name, metab, cons, mito, split, morph, chem, digest = row
            herb_dict[name] = HerbivoreProfile(
                metabolism_upkeep=metab,
                consumption_rate=cons,
                mitosis_threshold=mito,
                split_ratio=split,
                resistances={
                    "morphological_adaptation": morph,
                    "chemical_neutralization": chem,
                    "digestive_efficiency": digest,
                },
            )

        conn.close()
        return cls(data=BioDatabaseModel(flora=flora_dict, herbivores=herb_dict))

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
