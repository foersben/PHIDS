# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Condition evaluation logic for the signaling system."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from phids.engine.components.plant import PlantComponent
    from phids.engine.core.biotope import GridEnvironment
    from phids.engine.systems.signaling.types import ActivationNode


def _coerce_int(value: object, default: int) -> int:
    """Convert activation-node scalar payloads to int with deterministic fallback semantics."""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float, str)):
        try:
            return int(value)
        except ValueError:
            return default
    return default


def _coerce_float(value: object, default: float) -> float:
    """Convert activation-node scalar payloads to float with deterministic fallback semantics."""
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float, str)):
        try:
            return float(value)
        except ValueError:
            return default
    return default


def _is_substance_active_for_owner(
    owner_plant_id: int,
    substance_id: int,
    active_substance_ids_by_owner: dict[int, set[int]],
) -> bool:
    """Return whether a given substance is currently active on the owner plant."""
    return substance_id in active_substance_ids_by_owner.get(owner_plant_id, set())


def _eval_herbivore_presence(
    plant: PlantComponent,
    activation_condition: ActivationNode,
    swarm_population_by_cell_species: dict[tuple[int, int, int], int],
) -> bool:
    herbivore_species_id = _coerce_int(activation_condition.get("herbivore_species_id", -1), -1)
    min_herbivore_population = _coerce_int(activation_condition.get("min_herbivore_population", 1), 1)
    return swarm_population_by_cell_species.get((plant.x, plant.y, herbivore_species_id), 0) >= min_herbivore_population


def _eval_substance_active(
    owner_plant_id: int,
    activation_condition: ActivationNode,
    active_substance_ids_by_owner: dict[int, set[int]],
) -> bool:
    substance_id = _coerce_int(activation_condition.get("substance_id", -1), -1)
    return _is_substance_active_for_owner(
        owner_plant_id,
        substance_id,
        active_substance_ids_by_owner,
    )


def _eval_environmental_signal(
    plant: PlantComponent,
    activation_condition: ActivationNode,
    env: GridEnvironment,
) -> bool:
    signal_id = _coerce_int(activation_condition.get("signal_id", -1), -1)
    min_conc = _coerce_float(activation_condition.get("min_concentration", 0.01), 0.01)
    if 0 <= signal_id < env.num_signals:
        return float(env.signal_layers[signal_id, plant.x, plant.y]) >= min_conc
    return False


def _eval_all_of(
    plant: PlantComponent,
    owner_plant_id: int,
    activation_condition: ActivationNode,
    env: GridEnvironment,
    swarm_population_by_cell_species: dict[tuple[int, int, int], int],
    active_substance_ids_by_owner: dict[int, set[int]],
) -> bool:
    conditions = activation_condition.get("conditions", [])
    valid_conditions = (
        [child for child in conditions if isinstance(child, dict)] if isinstance(conditions, list) else []
    )
    return bool(valid_conditions) and all(
        _check_activation_condition(
            plant,
            owner_plant_id,
            cast("ActivationNode", child),
            env,
            swarm_population_by_cell_species,
            active_substance_ids_by_owner,
        )
        for child in valid_conditions
    )


def _eval_any_of(
    plant: PlantComponent,
    owner_plant_id: int,
    activation_condition: ActivationNode,
    env: GridEnvironment,
    swarm_population_by_cell_species: dict[tuple[int, int, int], int],
    active_substance_ids_by_owner: dict[int, set[int]],
) -> bool:
    conditions = activation_condition.get("conditions", [])
    valid_conditions = (
        [child for child in conditions if isinstance(child, dict)] if isinstance(conditions, list) else []
    )
    return any(
        _check_activation_condition(
            plant,
            owner_plant_id,
            cast("ActivationNode", child),
            env,
            swarm_population_by_cell_species,
            active_substance_ids_by_owner,
        )
        for child in valid_conditions
    )


def _check_activation_condition(
    plant: PlantComponent,
    owner_plant_id: int,
    activation_condition: ActivationNode | None,
    env: GridEnvironment,
    swarm_population_by_cell_species: dict[tuple[int, int, int], int],
    active_substance_ids_by_owner: dict[int, set[int]],
) -> bool:
    """Evaluate a nested activation predicate tree for one plant-owned substance.

    Recursively traverses the condition tree rooted at ``activation_condition``, evaluating
    ``herbivore_presence`` leaves against the per-cell herbivore census index, ``substance_active``
    leaves against the owner's active substance set, ``environmental_signal`` leaves against
    the current signal-layer concentration at the plant's coordinates, and ``all_of`` / ``any_of``
    composites using short-circuit Boolean logic.

    Args:
        plant: The plant entity whose grid coordinates are used for spatial condition checks.
        owner_plant_id: Entity identifier of the owning plant, used to look up currently active
            substances in ``active_substance_ids_by_owner``.
        activation_condition: JSON-serialisable condition node dictionary, or ``None`` for
            unconditional activation.
        env: ``GridEnvironment`` providing read access to signal-layer concentrations for
            ``environmental_signal`` predicates.
        swarm_population_by_cell_species: Pre-built census index mapping
            ``(x, y, species_id)`` to aggregate swarm population; used for ``herbivore_presence``
            evaluations without additional ECS world queries.
        active_substance_ids_by_owner: Mapping from plant entity id to its set of currently
            active substance layer indices; used for ``substance_active`` leaf evaluation.

    Returns:
        ``True`` when the condition tree evaluates to true; ``False`` otherwise.

    """
    if activation_condition is None:
        return True

    kind = activation_condition.get("kind")
    if kind == "herbivore_presence":
        return _eval_herbivore_presence(plant, activation_condition, swarm_population_by_cell_species)

    if kind == "substance_active":
        return _eval_substance_active(owner_plant_id, activation_condition, active_substance_ids_by_owner)

    if kind == "environmental_signal":
        return _eval_environmental_signal(plant, activation_condition, env)

    if kind == "all_of":
        return _eval_all_of(
            plant,
            owner_plant_id,
            activation_condition,
            env,
            swarm_population_by_cell_species,
            active_substance_ids_by_owner,
        )

    if kind == "any_of":
        return _eval_any_of(
            plant,
            owner_plant_id,
            activation_condition,
            env,
            swarm_population_by_cell_species,
            active_substance_ids_by_owner,
        )

    return False
