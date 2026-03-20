"""Server-side draft state model for the HTMX scenario-builder UI in PHIDS.

This module implements :class:`DraftState`, a server-side configuration accumulator for the PHIDS
scenario-builder UI. ``DraftState`` stores all operator choices made through the web interface,
including species definitions, substance properties, trigger rules, diet-matrix entries, and
initial placements, before committing them to the simulation engine via
``POST /api/scenario/load-draft``. Imperative mutation procedures are executed by
``DraftService`` (``phids.api.services.draft_service``) against ``DraftState`` instances, while
this module retains data structures, condition-tree utilities, schema export logic, and singleton
draft lifecycle management. No concurrency-safe locking is applied, as the server is designed for
single-operator workbench usage.
"""

from __future__ import annotations

import dataclasses
import logging
from copy import deepcopy
from typing import TYPE_CHECKING, Final, TypeAlias

if TYPE_CHECKING:
    from phids.api.schemas import (
        BatchJobState,
        FloraSpeciesParams,
        HerbivoreSpeciesParams,
        SimulationConfig,
    )

logger = logging.getLogger(__name__)

ConditionScalar: TypeAlias = str | int | float | bool
ConditionValue: TypeAlias = object
ActivationConditionNode: TypeAlias = dict[str, object]

# ---------------------------------------------------------------------------
# Substance definition (independent of any trigger coupling)
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class SubstanceDefinition:
    """Named substance with physical/biological properties.

    A substance definition captures how a chemical behaves once produced.
    The trigger matrix separately records *which* (flora, herbivore) pair
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
        min_herbivore_population: Minimum swarm size to trigger synthesis.
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
    min_herbivore_population: int = 5

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
        species_id: Herbivore species index.
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
    herbivore species *herbivore_species_id* with at least
    *min_herbivore_population* individuals, synthesise substance
    *substance_id*. Optional nested activation conditions can additionally
    require active substances and/or other herbivore presences via explicit
    ``all_of`` / ``any_of`` predicate trees. ``None`` = unconditional."

    Multiple rules may share the same (flora, herbivore) pair to express
    production of different substances simultaneously.

    Args:
        flora_species_id: Flora species index (0-based).
        herbivore_species_id: Herbivore species index (0-based).
        substance_id: Substance layer index to synthesise.
        min_herbivore_population: Minimum swarm size to trigger this rule.
        activation_condition: Optional JSON-serialisable predicate tree.
    """

    flora_species_id: int
    herbivore_species_id: int
    substance_id: int
    min_herbivore_population: int = 5
    activation_condition: ActivationConditionNode | None = None


def _legacy_signal_ids_to_activation_condition(
    required_signal_ids: list[int] | None,
) -> ActivationConditionNode | None:
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
    herbivore_species_id: int = 0,
    substance_id: int = 0,
    min_herbivore_population: int = 1,
) -> ActivationConditionNode:
    """Create a default activation-condition node of the requested kind."""
    if node_kind == "herbivore_presence":
        return {
            "kind": "herbivore_presence",
            "herbivore_species_id": herbivore_species_id,
            "min_herbivore_population": max(1, min_herbivore_population),
        }
    if node_kind == "substance_active":
        return {"kind": "substance_active", "substance_id": substance_id}
    if node_kind in {"all_of", "any_of"}:
        return {
            "kind": node_kind,
            "conditions": [
                _default_activation_condition_node(
                    "herbivore_presence",
                    herbivore_species_id=herbivore_species_id,
                    min_herbivore_population=min_herbivore_population,
                )
            ],
        }
    raise ValueError(f"Unsupported activation-condition node kind: {node_kind}")


def _condition_node_at_path(
    condition: ActivationConditionNode,
    path: list[int],
) -> ActivationConditionNode:
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


def _prune_empty_condition_groups(
    condition: ActivationConditionNode | None,
) -> ActivationConditionNode | None:
    """Remove empty nested groups after delete/remap operations."""
    if condition is None:
        return None
    if condition.get("kind") not in {"all_of", "any_of"}:
        return condition

    children = condition.get("conditions")
    if not isinstance(children, list):
        return None

    new_children: list[ActivationConditionNode] = []
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
    condition: ActivationConditionNode | None,
    *,
    removed_herbivore_id: int | None = None,
    removed_substance_id: int | None = None,
) -> ActivationConditionNode | None:
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
    if kind == "herbivore_presence":
        herbivore_species_id = _int_from_condition("herbivore_species_id")
        if removed_herbivore_id is not None:
            if herbivore_species_id == removed_herbivore_id:
                return None
            if herbivore_species_id > removed_herbivore_id:
                condition["herbivore_species_id"] = herbivore_species_id - 1
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
                    removed_herbivore_id=removed_herbivore_id,
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
    """Server-side draft configuration accumulator for the builder UI.

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
        z2_flora_species_extinction: Halt when this flora species goes extinct (-1 disables).
        z4_herbivore_species_extinction: Halt when this herbivore species goes extinct (-1 disables).
        z6_max_total_flora_energy: Halt when total flora energy exceeds this threshold (-1 disables).
        z7_max_total_herbivore_population: Halt when herbivore population exceeds this threshold
            (-1 disables).
        mycorrhizal_inter_species: Allow root connections across species.
        mycorrhizal_connection_cost: Energy to establish a root link.
        mycorrhizal_growth_interval_ticks: Ticks between root-growth attempts.
        mycorrhizal_signal_velocity: Signal hops per tick through roots.
        flora_species: Flora species parameter list (species_id == index).
        herbivore_species: Herbivore species parameter list (species_id == index).
        diet_matrix: Boolean matrix ``[herbivore_idx][flora_idx]`` for edibility.
        trigger_rules: List of explicit chemical-defense trigger rules.
            Multiple rules per (flora, herbivore) pair are allowed.
        substance_definitions: Named substance registry indexed by substance_id.
        initial_plants: Plants placed on the grid before simulation start.
        initial_swarms: Swarms placed on the grid before simulation start.
        active_batch_jobs: Registry of batch simulation jobs keyed by job_id.
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
    z2_flora_species_extinction: int = -1
    z4_herbivore_species_extinction: int = -1
    z6_max_total_flora_energy: float = -1.0
    z7_max_total_herbivore_population: int = -1
    mycorrhizal_inter_species: bool = False
    mycorrhizal_connection_cost: float = 1.0
    mycorrhizal_growth_interval_ticks: int = 8
    mycorrhizal_signal_velocity: int = 1
    flora_species: list[FloraSpeciesParams] = dataclasses.field(default_factory=list)
    herbivore_species: list[HerbivoreSpeciesParams] = dataclasses.field(default_factory=list)
    diet_matrix: list[list[bool]] = dataclasses.field(default_factory=list)
    trigger_rules: list[TriggerRule] = dataclasses.field(default_factory=list)
    substance_definitions: list[SubstanceDefinition] = dataclasses.field(default_factory=list)
    initial_plants: list[PlacedPlant] = dataclasses.field(default_factory=list)
    initial_swarms: list[PlacedSwarm] = dataclasses.field(default_factory=list)
    active_batch_jobs: dict[str, BatchJobState] = dataclasses.field(default_factory=dict)

    # ------------------------------------------------------------------
    # Config export
    # ------------------------------------------------------------------

    def build_sim_config(self) -> SimulationConfig:
        """Assemble a :class:`~phids.api.schemas.SimulationConfig`.

        Returns:
            SimulationConfig: Validated simulation configuration.

        Raises:
            ValueError: If no flora or herbivore species defined.
        """
        from phids.api.schemas import (
            DietCompatibilityMatrix,
            InitialPlantPlacement,
            InitialSwarmPlacement,
            SimulationConfig,
            TriggerConditionSchema,
        )

        if not self.flora_species or not self.herbivore_species:
            logger.warning(
                "Draft build rejected because required species are missing (flora=%d, herbivores=%d)",
                len(self.flora_species),
                len(self.herbivore_species),
            )
            raise ValueError("At least one flora and one herbivore species are required.")

        subs_by_id: dict[int, SubstanceDefinition] = {
            sd.substance_id: sd for sd in self.substance_definitions
        }

        # Group trigger rules by flora_species_id
        triggers_by_flora: dict[int, list[TriggerConditionSchema]] = {}
        for rule in self.trigger_rules:
            sd = subs_by_id.get(rule.substance_id)
            if sd is None:
                logger.warning(
                    "Skipping trigger rule with missing substance definition (flora_species_id=%d, herbivore_species_id=%d, substance_id=%d)",
                    rule.flora_species_id,
                    rule.herbivore_species_id,
                    rule.substance_id,
                )
                continue
            triggers_by_flora.setdefault(rule.flora_species_id, []).append(
                TriggerConditionSchema(
                    herbivore_species_id=rule.herbivore_species_id,
                    min_herbivore_population=rule.min_herbivore_population,
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
            triggers = triggers_by_flora.get(fp.species_id, [])
            flora_with_triggers.append(fp.model_copy(update={"triggers": triggers}))

        n_herbivore = len(self.herbivore_species)
        n_flora = len(flora_with_triggers)
        diet_rows = [
            (self.diet_matrix[pi][:n_flora] if pi < len(self.diet_matrix) else [False] * n_flora)
            for pi in range(n_herbivore)
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
            herbivore_species=self.herbivore_species,
            diet_matrix=DietCompatibilityMatrix(rows=diet_rows),
            initial_plants=plant_placements,
            initial_swarms=swarm_placements,
            mycorrhizal_inter_species=self.mycorrhizal_inter_species,
            mycorrhizal_connection_cost=self.mycorrhizal_connection_cost,
            mycorrhizal_growth_interval_ticks=self.mycorrhizal_growth_interval_ticks,
            mycorrhizal_signal_velocity=self.mycorrhizal_signal_velocity,
            z2_flora_species_extinction=self.z2_flora_species_extinction,
            z4_herbivore_species_extinction=self.z4_herbivore_species_extinction,
            z6_max_total_flora_energy=self.z6_max_total_flora_energy,
            z7_max_total_herbivore_population=self.z7_max_total_herbivore_population,
        )
        logger.info(
            "Draft converted to SimulationConfig (grid=%dx%d, flora=%d, herbivores=%d, trigger_rules=%d, plants=%d, swarms=%d)",
            self.grid_width,
            self.grid_height,
            len(flora_with_triggers),
            len(self.herbivore_species),
            len(self.trigger_rules),
            len(self.initial_plants),
            len(self.initial_swarms),
        )
        return config

    @classmethod
    def default(cls) -> DraftState:
        """Create the built-in default draft state."""
        from phids.api.schemas import FloraSpeciesParams, HerbivoreSpeciesParams

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
            herbivore_species=[
                HerbivoreSpeciesParams(
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
        "Draft state replaced (scenario_name=%s, flora=%d, herbivores=%d, substances=%d)",
        state.scenario_name,
        len(state.flora_species),
        len(state.herbivore_species),
        len(state.substance_definitions),
    )


def reset_draft() -> None:
    """Reset the draft state to the built-in default."""
    global _draft  # noqa: PLW0603
    _draft = DraftState.default()
    logger.info("Draft state reset to built-in default scenario")
