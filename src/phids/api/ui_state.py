"""
Server-side mutable draft state for the HTMX scenario-builder UI in PHIDS.

This module implements the DraftState, a mutable server-side configuration accumulator for the PHIDS scenario-builder UI. The DraftState collects all operator choices made through the web interface, including species, substances, trigger rules, and placements, before committing them to the simulation engine via POST /api/scenario/load-draft. The module exposes a single global DraftState instance, accessed through get_draft and reset_draft, which is mutated directly by route handlers. No concurrency-safe locking is applied, as the server is designed for single-operator workbench usage. The architectural design ensures deterministic scenario construction, reproducibility, and scientific integrity, supporting rigorous validation and compliance with the Rule of 16, O(1) spatial hash invariants, and double-buffered simulation logic. The module is central to the UI’s ability to model complex ecological dynamics and emergent behaviors with maximal biological fidelity.

This module-level docstring is written in accordance with Google-style documentation standards, providing a comprehensive scholarly abstract of the DraftState's architectural role, algorithmic mechanics, and biological rationale.
"""

from __future__ import annotations

import dataclasses
import logging
from copy import deepcopy
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from phids.api.schemas import SimulationConfig

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Substance definition (independent of any trigger coupling)
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class SubstanceDefinition:
    """Named substance with physical/biological properties.

    A substance definition captures how a chemical behaves once produced.
    The trigger matrix separately records *which* (flora, predator) pair
    activates synthesis.

    Args:
        substance_id: Layer index in ``GridEnvironment.signal_layers`` or
            ``toxin_layers`` (0 ≤ id < MAX_SUBSTANCE_TYPES).
        name: Human-readable label shown in the UI.
        is_toxin: ``True`` for toxins; ``False`` for airborne signals.
        lethal: Lethal-toxin flag (ignored if ``is_toxin`` is ``False``).
        repellent: Repellent-toxin flag.
        synthesis_duration: Ticks to complete synthesis (production time).
        aftereffect_ticks: Ticks the substance lingers after emission ceases.
        lethality_rate: Population units eliminated per tick (β).
        repellent_walk_ticks: Random-walk duration on repel trigger.
        energy_cost_per_tick: Energy drained from the plant per active tick.
        irreversible: Keep the substance active permanently once activated.
        precursor_signal_id: Signal id required before activation (−1 = none).
        min_predator_population: Minimum swarm size to trigger synthesis.
    """

    substance_id: int
    name: str = "Signal"
    is_toxin: bool = False
    lethal: bool = False
    repellent: bool = False
    synthesis_duration: int = 3
    aftereffect_ticks: int = 0
    lethality_rate: float = 0.0
    repellent_walk_ticks: int = 3
    energy_cost_per_tick: float = 1.0
    irreversible: bool = False
    precursor_signal_id: int = -1
    min_predator_population: int = 5

    @property
    def type_label(self) -> str:
        """Human-readable substance type.

        Returns:
            str: One of ``"Signal"``, ``"Lethal Toxin"``,
                ``"Repellent Toxin"``, or ``"Toxin"``.
        """
        if not self.is_toxin:
            return "Signal"
        if self.lethal:
            return "Lethal Toxin"
        if self.repellent:
            return "Repellent Toxin"
        return "Toxin"


# ---------------------------------------------------------------------------
# Placement dataclasses
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class PlacedPlant:
    """A plant placed on the grid before the simulation starts.

    Args:
        species_id: Flora species index.
        x: Grid x-coordinate.
        y: Grid y-coordinate.
        energy: Initial energy reserve.
    """

    species_id: int
    x: int
    y: int
    energy: float


@dataclasses.dataclass
class PlacedSwarm:
    """A herbivore swarm placed on the grid before the simulation starts.

    Args:
        species_id: Predator species index.
        x: Grid x-coordinate.
        y: Grid y-coordinate.
        population: Initial swarm population.
        energy: Initial energy reserve.
    """

    species_id: int
    x: int
    y: int
    population: int
    energy: float


# ---------------------------------------------------------------------------
# Trigger rule
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class TriggerRule:
    """One explicit chemical-defense trigger rule.

    A rule says: "when flora species *flora_species_id* is attacked by
    predator species *predator_species_id* with at least
    *min_predator_population* individuals, synthesise substance
    *substance_id*. Optional nested activation conditions can additionally
    require active substances and/or other enemy presences via explicit
    ``all_of`` / ``any_of`` predicate trees. ``None`` = unconditional."

    Multiple rules may share the same (flora, predator) pair to express
    production of different substances simultaneously.

    Args:
        flora_species_id: Flora species index (0-based).
        predator_species_id: Predator species index (0-based).
        substance_id: Substance layer index to synthesise.
        min_predator_population: Minimum swarm size to trigger this rule.
        activation_condition: Optional JSON-serialisable predicate tree.
    """

    flora_species_id: int
    predator_species_id: int
    substance_id: int
    min_predator_population: int = 5
    activation_condition: dict[str, object] | None = None


def _legacy_signal_ids_to_activation_condition(
    required_signal_ids: list[int] | None,
) -> dict[str, object] | None:
    """Convert legacy signal-only precursor gates into the richer tree form."""
    signal_ids = [signal_id for signal_id in (required_signal_ids or []) if signal_id >= 0]
    if not signal_ids:
        return None
    leaves = [{"kind": "substance_active", "substance_id": signal_id} for signal_id in signal_ids]
    return leaves[0] if len(leaves) == 1 else {"kind": "all_of", "conditions": leaves}


def _parse_condition_path(path: str) -> list[int]:
    """Parse a dotted child-path like ``0.1.2`` into list indices."""
    if not path:
        return []
    return [int(part) for part in path.split(".") if part != ""]


def _default_activation_condition_node(
    node_kind: str,
    *,
    predator_species_id: int = 0,
    substance_id: int = 0,
    min_predator_population: int = 1,
) -> dict[str, object]:
    """Create a default activation-condition node of the requested kind."""
    if node_kind == "enemy_presence":
        return {
            "kind": "enemy_presence",
            "predator_species_id": predator_species_id,
            "min_predator_population": max(1, min_predator_population),
        }
    if node_kind == "substance_active":
        return {"kind": "substance_active", "substance_id": substance_id}
    if node_kind in {"all_of", "any_of"}:
        return {
            "kind": node_kind,
            "conditions": [
                _default_activation_condition_node(
                    "enemy_presence",
                    predator_species_id=predator_species_id,
                    min_predator_population=min_predator_population,
                )
            ],
        }
    raise ValueError(f"Unsupported activation-condition node kind: {node_kind}")


def _condition_node_at_path(
    condition: dict[str, object],
    path: list[int],
) -> dict[str, object]:
    """Return the condition node at ``path`` or raise on invalid traversal."""
    node = condition
    for index in path:
        if node.get("kind") not in {"all_of", "any_of"}:
            raise IndexError("Condition path traversed into a non-group node.")
        children = node.get("conditions")
        if not isinstance(children, list) or index < 0 or index >= len(children):
            raise IndexError("Condition path index is out of range.")
        child = children[index]
        if not isinstance(child, dict):
            raise IndexError("Condition path resolved to an invalid child node.")
        node = child
    return node


def _prune_empty_condition_groups(condition: dict[str, object] | None) -> dict[str, object] | None:
    """Remove empty nested groups after delete/remap operations."""
    if condition is None:
        return None
    if condition.get("kind") not in {"all_of", "any_of"}:
        return condition

    children = condition.get("conditions")
    if not isinstance(children, list):
        return None

    new_children: list[dict[str, object]] = []
    for child in children:
        if not isinstance(child, dict):
            continue
        pruned = _prune_empty_condition_groups(child)
        if pruned is not None:
            new_children.append(pruned)
    if not new_children:
        return None
    condition["conditions"] = new_children
    return condition


def _remap_condition_references(
    condition: dict[str, object] | None,
    *,
    removed_predator_id: int | None = None,
    removed_substance_id: int | None = None,
) -> dict[str, object] | None:
    """Compact/remove nested condition references after entity deletion."""
    if condition is None:
        return None

    def _int_from_condition(key: str, default: int = -1) -> int:
        raw = condition.get(key, default)
        if isinstance(raw, bool):
            return default
        if isinstance(raw, (int, float, str)):
            try:
                return int(raw)
            except ValueError:
                return default
        return default

    kind = condition.get("kind")
    if kind == "enemy_presence":
        predator_species_id = _int_from_condition("predator_species_id")
        if removed_predator_id is not None:
            if predator_species_id == removed_predator_id:
                return None
            if predator_species_id > removed_predator_id:
                condition["predator_species_id"] = predator_species_id - 1
        return condition
    if kind == "substance_active":
        substance_id = _int_from_condition("substance_id")
        if removed_substance_id is not None:
            if substance_id == removed_substance_id:
                return None
            if substance_id > removed_substance_id:
                condition["substance_id"] = substance_id - 1
        return condition

    if kind in {"all_of", "any_of"}:
        children = condition.get("conditions")
        if not isinstance(children, list):
            return None
        condition["conditions"] = [
            pruned
            for child in children
            if isinstance(child, dict)
            for pruned in [
                _remap_condition_references(
                    child,
                    removed_predator_id=removed_predator_id,
                    removed_substance_id=removed_substance_id,
                )
            ]
            if pruned is not None
        ]
        return _prune_empty_condition_groups(condition)
    return condition


# ---------------------------------------------------------------------------
# Draft state
# ---------------------------------------------------------------------------

_DEFAULT_SCENARIO_NAME: Final[str] = "Default Scenario"


@dataclasses.dataclass
class DraftState:
    """Mutable server-side configuration accumulator for the builder UI.

    Attributes:
        scenario_name: Human-readable label used in the UI header.
        grid_width: Biotope width in cells (1–80).
        grid_height: Biotope height in cells (1–80).
        max_ticks: Simulation tick budget.
        tick_rate_hz: WebSocket streaming rate in ticks per second.
        wind_x: Initial uniform wind x-component.
        wind_y: Initial uniform wind y-component.
        num_signals: Number of airborne signal layers.
        num_toxins: Number of toxin layers.
        mycorrhizal_inter_species: Allow root connections across species.
        mycorrhizal_connection_cost: Energy to establish a root link.
        mycorrhizal_growth_interval_ticks: Ticks between root-growth attempts.
        mycorrhizal_signal_velocity: Signal hops per tick through roots.
        flora_species: Flora species parameter list (species_id == index).
        predator_species: Predator species parameter list (species_id == index).
        diet_matrix: Boolean matrix ``[pred_idx][flora_idx]`` for edibility.
        trigger_rules: List of explicit chemical-defense trigger rules.
            Multiple rules per (flora, predator) pair are allowed.
        substance_definitions: Named substance registry indexed by substance_id.
        initial_plants: Plants placed on the grid before simulation start.
        initial_swarms: Swarms placed on the grid before simulation start.
    """

    scenario_name: str = _DEFAULT_SCENARIO_NAME
    grid_width: int = 40
    grid_height: int = 40
    max_ticks: int = 1000
    tick_rate_hz: float = 10.0
    wind_x: float = 0.0
    wind_y: float = 0.0
    num_signals: int = 4
    num_toxins: int = 4
    mycorrhizal_inter_species: bool = False
    mycorrhizal_connection_cost: float = 1.0
    mycorrhizal_growth_interval_ticks: int = 8
    mycorrhizal_signal_velocity: int = 1
    flora_species: list[object] = dataclasses.field(default_factory=list)
    predator_species: list[object] = dataclasses.field(default_factory=list)
    diet_matrix: list[list[bool]] = dataclasses.field(default_factory=list)
    trigger_rules: list[TriggerRule] = dataclasses.field(default_factory=list)
    substance_definitions: list[SubstanceDefinition] = dataclasses.field(default_factory=list)
    initial_plants: list[PlacedPlant] = dataclasses.field(default_factory=list)
    initial_swarms: list[PlacedSwarm] = dataclasses.field(default_factory=list)

    # ------------------------------------------------------------------
    # Matrix resize helpers (diet_matrix only now)
    # ------------------------------------------------------------------

    def _resize_diet_matrix(self) -> None:
        """Resize diet matrix to match species list lengths."""
        n_pred = len(self.predator_species)
        n_flora = len(self.flora_species)

        while len(self.diet_matrix) < n_pred:
            self.diet_matrix.append([False] * n_flora)
        self.diet_matrix = self.diet_matrix[:n_pred]
        for row in self.diet_matrix:
            while len(row) < n_flora:
                row.append(False)
            del row[n_flora:]

    def rebuild_species_ids(self) -> None:
        """Re-assign sequential ``species_id`` values after list mutation."""
        from phids.api.schemas import FloraSpeciesParams, PredatorSpeciesParams

        self.flora_species = [
            fp.model_copy(update={"species_id": i})
            for i, fp in enumerate(self.flora_species)
            if isinstance(fp, FloraSpeciesParams)
        ]
        self.predator_species = [
            pp.model_copy(update={"species_id": i})
            for i, pp in enumerate(self.predator_species)
            if isinstance(pp, PredatorSpeciesParams)
        ]

    # ------------------------------------------------------------------
    # Species mutation helpers
    # ------------------------------------------------------------------

    def add_flora(self, params: object) -> None:
        """Append a flora species and extend the diet matrix.

        Args:
            params: :class:`~phids.api.schemas.FloraSpeciesParams`.
        """
        self.flora_species.append(params)
        self.rebuild_species_ids()
        self._resize_diet_matrix()
        logger.debug(
            "Draft flora added (species_id=%s, total_flora=%d)",
            getattr(params, "species_id", "?"),
            len(self.flora_species),
        )

    def remove_flora(self, species_id: int) -> None:
        """Remove a flora species by id and clean up dependent data.

        Args:
            species_id: The ``species_id`` of the species to remove.

        Raises:
            ValueError: If no species with the given id exists.
        """
        from phids.api.schemas import FloraSpeciesParams

        idx = next(
            (
                i
                for i, fp in enumerate(self.flora_species)
                if isinstance(fp, FloraSpeciesParams) and fp.species_id == species_id
            ),
            None,
        )
        if idx is None:
            raise ValueError(f"Flora species_id {species_id} not found.")

        del self.flora_species[idx]
        # Remove diet_matrix column for this flora species
        for row in self.diet_matrix:
            if idx < len(row):
                del row[idx]

        # Remove trigger rules referencing this flora species; compact higher IDs
        new_rules: list[TriggerRule] = []
        for rule in self.trigger_rules:
            if rule.flora_species_id == species_id:
                continue  # orphaned rule
            new_rule = dataclasses.replace(rule)
            if new_rule.flora_species_id > species_id:
                new_rule.flora_species_id -= 1  # compact after removal
            new_rules.append(new_rule)
        self.trigger_rules = new_rules

        # Remove placements
        self.initial_plants = [p for p in self.initial_plants if p.species_id != species_id]
        self.rebuild_species_ids()
        self._resize_diet_matrix()
        logger.debug(
            "Draft flora removed (species_id=%d, total_flora=%d, remaining_trigger_rules=%d)",
            species_id,
            len(self.flora_species),
            len(self.trigger_rules),
        )

    def add_predator(self, params: object) -> None:
        """Append a predator species and extend the diet matrix.

        Args:
            params: :class:`~phids.api.schemas.PredatorSpeciesParams`.
        """
        self.predator_species.append(params)
        self.rebuild_species_ids()
        self._resize_diet_matrix()
        logger.debug(
            "Draft predator added (species_id=%s, total_predators=%d)",
            getattr(params, "species_id", "?"),
            len(self.predator_species),
        )

    def remove_predator(self, species_id: int) -> None:
        """Remove a predator species by id and clean up dependent data.

        Args:
            species_id: The ``species_id`` of the species to remove.

        Raises:
            ValueError: If no species with the given id exists.
        """
        from phids.api.schemas import PredatorSpeciesParams

        idx = next(
            (
                i
                for i, pp in enumerate(self.predator_species)
                if isinstance(pp, PredatorSpeciesParams) and pp.species_id == species_id
            ),
            None,
        )
        if idx is None:
            raise ValueError(f"Predator species_id {species_id} not found.")

        del self.predator_species[idx]
        # Remove diet_matrix row for this predator
        if idx < len(self.diet_matrix):
            del self.diet_matrix[idx]

        # Remove trigger rules referencing this predator; compact higher IDs
        new_rules: list[TriggerRule] = []
        for rule in self.trigger_rules:
            if rule.predator_species_id == species_id:
                continue  # orphaned rule
            new_rule = dataclasses.replace(rule)
            if new_rule.predator_species_id > species_id:
                new_rule.predator_species_id -= 1
            new_rule.activation_condition = _remap_condition_references(
                deepcopy(new_rule.activation_condition),
                removed_predator_id=species_id,
            )
            new_rules.append(new_rule)
        self.trigger_rules = new_rules

        # Remove placements
        self.initial_swarms = [s for s in self.initial_swarms if s.species_id != species_id]
        self.rebuild_species_ids()
        self._resize_diet_matrix()
        logger.debug(
            "Draft predator removed (species_id=%d, total_predators=%d, remaining_trigger_rules=%d)",
            species_id,
            len(self.predator_species),
            len(self.trigger_rules),
        )

    # ------------------------------------------------------------------
    # Trigger rule helpers
    # ------------------------------------------------------------------

    def add_trigger_rule(
        self,
        flora_species_id: int,
        predator_species_id: int,
        substance_id: int,
        min_predator_population: int = 5,
        activation_condition: dict[str, object] | None = None,
        required_signal_ids: list[int] | None = None,
    ) -> None:
        """Append a new trigger rule.

        Args:
            flora_species_id: Flora species index.
            predator_species_id: Predator species index.
            substance_id: Substance to synthesise.
            min_predator_population: Minimum swarm size threshold.
            activation_condition: Optional nested predicate tree.
            required_signal_ids: Deprecated compatibility shorthand for
                signal-only AND gates.
        """
        self.trigger_rules.append(
            TriggerRule(
                flora_species_id=flora_species_id,
                predator_species_id=predator_species_id,
                substance_id=substance_id,
                min_predator_population=min_predator_population,
                activation_condition=deepcopy(
                    activation_condition
                    if activation_condition is not None
                    else _legacy_signal_ids_to_activation_condition(required_signal_ids)
                ),
            )
        )
        logger.debug(
            "Draft trigger rule added (flora_species_id=%d, predator_species_id=%d, substance_id=%d, total_rules=%d)",
            flora_species_id,
            predator_species_id,
            substance_id,
            len(self.trigger_rules),
        )

    def remove_trigger_rule(self, index: int) -> None:
        """Remove a trigger rule by list index.

        Args:
            index: Position in the trigger_rules list.

        Raises:
            IndexError: If index is out of range.
        """
        removed = self.trigger_rules[index]
        del self.trigger_rules[index]
        logger.debug(
            "Draft trigger rule removed (index=%d, flora_species_id=%d, predator_species_id=%d, substance_id=%d, total_rules=%d)",
            index,
            removed.flora_species_id,
            removed.predator_species_id,
            removed.substance_id,
            len(self.trigger_rules),
        )

    def update_trigger_rule(
        self,
        index: int,
        *,
        flora_species_id: int | None = None,
        predator_species_id: int | None = None,
        substance_id: int | None = None,
        min_predator_population: int | None = None,
        activation_condition: dict[str, object] | None = None,
        required_signal_ids: list[int] | None = None,
    ) -> None:
        """Update fields of a trigger rule in-place.

        Args:
            index: Position in the trigger_rules list.
            flora_species_id: New flora species id (optional).
            predator_species_id: New predator species id (optional).
            substance_id: New substance id (optional).
            min_predator_population: New minimum population (optional).
            activation_condition: New condition tree (optional).
            required_signal_ids: Deprecated compatibility shorthand for
                signal-only AND gates.

        Raises:
            IndexError: If index is out of range.
        """
        rule = self.trigger_rules[index]
        if flora_species_id is not None:
            rule.flora_species_id = flora_species_id
        if predator_species_id is not None:
            rule.predator_species_id = predator_species_id
        if substance_id is not None:
            rule.substance_id = substance_id
        if min_predator_population is not None:
            rule.min_predator_population = min_predator_population
        if activation_condition is not None:
            rule.activation_condition = deepcopy(activation_condition)
        elif required_signal_ids is not None:
            rule.activation_condition = _legacy_signal_ids_to_activation_condition(
                required_signal_ids
            )
        logger.debug(
            "Draft trigger rule updated (index=%d, flora_species_id=%d, predator_species_id=%d, substance_id=%d)",
            index,
            rule.flora_species_id,
            rule.predator_species_id,
            rule.substance_id,
        )

    def set_trigger_rule_activation_condition(
        self,
        index: int,
        condition: dict[str, object] | None,
    ) -> None:
        """Replace the full activation-condition tree for one trigger rule."""
        self.trigger_rules[index].activation_condition = deepcopy(condition)

    def replace_trigger_rule_condition_node(
        self,
        index: int,
        path: str,
        condition: dict[str, object],
    ) -> None:
        """Replace the node at ``path`` inside one trigger rule's condition tree."""
        rule = self.trigger_rules[index]
        if not path:
            rule.activation_condition = deepcopy(condition)
            return
        if rule.activation_condition is None:
            raise IndexError("Trigger rule has no activation condition to replace.")
        root = deepcopy(rule.activation_condition)
        path_indices = _parse_condition_path(path)
        parent = _condition_node_at_path(root, path_indices[:-1])
        if parent.get("kind") not in {"all_of", "any_of"}:
            raise IndexError("Condition parent is not a group node.")
        children = parent.get("conditions")
        if not isinstance(children, list):
            raise IndexError("Condition parent has no child list.")
        child_index = path_indices[-1]
        if child_index < 0 or child_index >= len(children):
            raise IndexError("Condition node index is out of range.")
        children[child_index] = deepcopy(condition)
        rule.activation_condition = root

    def append_trigger_rule_condition_child(
        self,
        index: int,
        parent_path: str,
        condition: dict[str, object],
    ) -> None:
        """Append a child node to a group within one trigger rule's condition tree."""
        rule = self.trigger_rules[index]
        if rule.activation_condition is None:
            raise IndexError("Trigger rule has no activation condition to append to.")
        root = deepcopy(rule.activation_condition)
        parent = _condition_node_at_path(root, _parse_condition_path(parent_path))
        if parent.get("kind") not in {"all_of", "any_of"}:
            raise IndexError("Condition parent is not a group node.")
        children = parent.setdefault("conditions", [])
        if not isinstance(children, list):
            raise IndexError("Condition parent has an invalid child list.")
        children.append(deepcopy(condition))
        rule.activation_condition = root

    def delete_trigger_rule_condition_node(self, index: int, path: str) -> None:
        """Delete the node at ``path`` from one trigger rule's condition tree."""
        rule = self.trigger_rules[index]
        if rule.activation_condition is None:
            return
        if not path:
            rule.activation_condition = None
            return
        root = deepcopy(rule.activation_condition)
        path_indices = _parse_condition_path(path)
        parent = _condition_node_at_path(root, path_indices[:-1])
        if parent.get("kind") not in {"all_of", "any_of"}:
            raise IndexError("Condition parent is not a group node.")
        children = parent.get("conditions")
        if not isinstance(children, list):
            raise IndexError("Condition parent has no child list.")
        child_index = path_indices[-1]
        if child_index < 0 or child_index >= len(children):
            raise IndexError("Condition node index is out of range.")
        del children[child_index]
        rule.activation_condition = _prune_empty_condition_groups(root)

    def update_trigger_rule_condition_node(
        self,
        index: int,
        path: str,
        **fields: object,
    ) -> None:
        """Patch selected fields on the condition node at ``path``."""
        rule = self.trigger_rules[index]
        if rule.activation_condition is None:
            raise IndexError("Trigger rule has no activation condition to update.")
        root = deepcopy(rule.activation_condition)
        node = _condition_node_at_path(root, _parse_condition_path(path))
        node.update(fields)
        rule.activation_condition = root

    # ------------------------------------------------------------------
    # Placement helpers
    # ------------------------------------------------------------------

    def add_plant_placement(self, species_id: int, x: int, y: int, energy: float) -> None:
        """Add a plant placement to the draft."""
        self.initial_plants.append(PlacedPlant(species_id=species_id, x=x, y=y, energy=energy))
        logger.debug(
            "Draft plant placement added (species_id=%d, x=%d, y=%d, total_plants=%d)",
            species_id,
            x,
            y,
            len(self.initial_plants),
        )

    def add_swarm_placement(
        self, species_id: int, x: int, y: int, population: int, energy: float
    ) -> None:
        """Add a swarm placement to the draft."""
        self.initial_swarms.append(
            PlacedSwarm(
                species_id=species_id,
                x=x,
                y=y,
                population=population,
                energy=energy,
            )
        )
        logger.debug(
            "Draft swarm placement added (species_id=%d, x=%d, y=%d, population=%d, total_swarms=%d)",
            species_id,
            x,
            y,
            population,
            len(self.initial_swarms),
        )

    def remove_plant_placement(self, index: int) -> None:
        """Remove a plant placement by list index."""
        removed = self.initial_plants[index]
        del self.initial_plants[index]
        logger.debug(
            "Draft plant placement removed (index=%d, species_id=%d, x=%d, y=%d, total_plants=%d)",
            index,
            removed.species_id,
            removed.x,
            removed.y,
            len(self.initial_plants),
        )

    def remove_swarm_placement(self, index: int) -> None:
        """Remove a swarm placement by list index."""
        removed = self.initial_swarms[index]
        del self.initial_swarms[index]
        logger.debug(
            "Draft swarm placement removed (index=%d, species_id=%d, x=%d, y=%d, total_swarms=%d)",
            index,
            removed.species_id,
            removed.x,
            removed.y,
            len(self.initial_swarms),
        )

    def clear_placements(self) -> None:
        """Remove all plant and swarm placements."""
        cleared_plants = len(self.initial_plants)
        cleared_swarms = len(self.initial_swarms)
        self.initial_plants.clear()
        self.initial_swarms.clear()
        logger.debug(
            "Draft placements cleared (plants=%d, swarms=%d)",
            cleared_plants,
            cleared_swarms,
        )

    # ------------------------------------------------------------------
    # Config export
    # ------------------------------------------------------------------

    def build_sim_config(self) -> SimulationConfig:
        """Assemble a :class:`~phids.api.schemas.SimulationConfig`.

        Returns:
            SimulationConfig: Validated simulation configuration.

        Raises:
            ValueError: If no flora or predator species defined.
        """
        from phids.api.schemas import (
            DietCompatibilityMatrix,
            FloraSpeciesParams,
            InitialPlantPlacement,
            InitialSwarmPlacement,
            PredatorSpeciesParams,
            SimulationConfig,
            TriggerConditionSchema,
        )

        if not self.flora_species or not self.predator_species:
            logger.warning(
                "Draft build rejected because required species are missing (flora=%d, predators=%d)",
                len(self.flora_species),
                len(self.predator_species),
            )
            raise ValueError("At least one flora and one predator species are required.")

        subs_by_id: dict[int, SubstanceDefinition] = {
            sd.substance_id: sd for sd in self.substance_definitions
        }

        # Group trigger rules by flora_species_id
        triggers_by_flora: dict[int, list[TriggerConditionSchema]] = {}
        for rule in self.trigger_rules:
            sd = subs_by_id.get(rule.substance_id)
            if sd is None:
                logger.warning(
                    "Skipping trigger rule with missing substance definition (flora_species_id=%d, predator_species_id=%d, substance_id=%d)",
                    rule.flora_species_id,
                    rule.predator_species_id,
                    rule.substance_id,
                )
                continue
            triggers_by_flora.setdefault(rule.flora_species_id, []).append(
                TriggerConditionSchema(
                    predator_species_id=rule.predator_species_id,
                    min_predator_population=rule.min_predator_population,
                    substance_id=rule.substance_id,
                    synthesis_duration=sd.synthesis_duration,
                    is_toxin=sd.is_toxin,
                    lethal=sd.lethal,
                    lethality_rate=sd.lethality_rate,
                    repellent=sd.repellent,
                    repellent_walk_ticks=sd.repellent_walk_ticks,
                    aftereffect_ticks=sd.aftereffect_ticks,
                    activation_condition=deepcopy(rule.activation_condition),
                    energy_cost_per_tick=sd.energy_cost_per_tick,
                    irreversible=sd.irreversible,
                )
            )

        flora_with_triggers: list[FloraSpeciesParams] = []
        for fp in self.flora_species:
            if not isinstance(fp, FloraSpeciesParams):
                continue
            triggers = triggers_by_flora.get(fp.species_id, [])
            flora_with_triggers.append(fp.model_copy(update={"triggers": triggers}))

        n_pred = len(self.predator_species)
        n_flora = len(flora_with_triggers)
        diet_rows = [
            (self.diet_matrix[pi][:n_flora] if pi < len(self.diet_matrix) else [False] * n_flora)
            for pi in range(n_pred)
        ]

        plant_placements = [
            InitialPlantPlacement(species_id=p.species_id, x=p.x, y=p.y, energy=p.energy)
            for p in self.initial_plants
        ]
        swarm_placements = [
            InitialSwarmPlacement(
                species_id=s.species_id,
                x=s.x,
                y=s.y,
                population=s.population,
                energy=s.energy,
            )
            for s in self.initial_swarms
        ]

        config = SimulationConfig(
            grid_width=self.grid_width,
            grid_height=self.grid_height,
            max_ticks=self.max_ticks,
            tick_rate_hz=self.tick_rate_hz,
            num_signals=self.num_signals,
            num_toxins=self.num_toxins,
            wind_x=self.wind_x,
            wind_y=self.wind_y,
            flora_species=flora_with_triggers,
            predator_species=[
                pp for pp in self.predator_species if isinstance(pp, PredatorSpeciesParams)
            ],
            diet_matrix=DietCompatibilityMatrix(rows=diet_rows),
            initial_plants=plant_placements,
            initial_swarms=swarm_placements,
            mycorrhizal_inter_species=self.mycorrhizal_inter_species,
            mycorrhizal_connection_cost=self.mycorrhizal_connection_cost,
            mycorrhizal_growth_interval_ticks=self.mycorrhizal_growth_interval_ticks,
            mycorrhizal_signal_velocity=self.mycorrhizal_signal_velocity,
        )
        logger.info(
            "Draft converted to SimulationConfig (grid=%dx%d, flora=%d, predators=%d, trigger_rules=%d, plants=%d, swarms=%d)",
            self.grid_width,
            self.grid_height,
            len(flora_with_triggers),
            len(self.predator_species),
            len(self.trigger_rules),
            len(self.initial_plants),
            len(self.initial_swarms),
        )
        return config

    @classmethod
    def default(cls) -> DraftState:
        """Create the built-in default draft state."""
        from phids.api.schemas import FloraSpeciesParams, PredatorSpeciesParams

        state = cls(
            flora_species=[
                FloraSpeciesParams(
                    species_id=0,
                    name="Grass",
                    base_energy=10.0,
                    max_energy=100.0,
                    growth_rate=5.0,
                    survival_threshold=1.0,
                    reproduction_interval=10,
                    seed_min_dist=1.0,
                    seed_max_dist=3.0,
                    seed_energy_cost=5.0,
                    triggers=[],
                )
            ],
            predator_species=[
                PredatorSpeciesParams(
                    species_id=0,
                    name="Herbivore",
                    energy_min=5.0,
                    velocity=2,
                    consumption_rate=10.0,
                )
            ],
            diet_matrix=[[True]],
            trigger_rules=[],
            substance_definitions=[],
            initial_plants=[],
            initial_swarms=[],
        )
        return state


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_draft: DraftState | None = None


def get_draft() -> DraftState:
    """Return the current draft state, initialising a default if needed.

    Returns:
        DraftState: The active draft configuration.
    """
    global _draft  # noqa: PLW0603
    if _draft is None:
        _draft = DraftState.default()
        logger.info("Draft state initialised with built-in default scenario")
    return _draft


def set_draft(state: DraftState) -> None:
    """Replace the active draft state.

    Args:
        state: New :class:`DraftState` to activate.
    """
    global _draft  # noqa: PLW0603
    _draft = state
    logger.info(
        "Draft state replaced (scenario_name=%s, flora=%d, predators=%d, substances=%d)",
        state.scenario_name,
        len(state.flora_species),
        len(state.predator_species),
        len(state.substance_definitions),
    )


def reset_draft() -> None:
    """Reset the draft state to the built-in default."""
    global _draft  # noqa: PLW0603
    _draft = DraftState.default()
    logger.info("Draft state reset to built-in default scenario")
