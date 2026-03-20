"""Entity-Component-System (ECS) registry with O(1) spatial hash support for deterministic ecosystem simulation.

This module implements the :class:`ECSWorld` registry, a flat entity-component system designed to
maximise computational efficiency and biological fidelity in the PHIDS simulation engine. The ECS
maintains a flat entity registry, per-component type indices for rapid multi-component queries,
and a spatial hash grid enabling O(1) membership lookups for entities occupying a given cell. This
architecture is essential for simulating plant-herbivore interactions, metabolic attrition, and
systemic acquired resistance without incurring O(N²) locality costs. The design strictly adheres
to data-oriented principles, avoiding Python object graphs in favour of flat dataclass-backed
components and pre-allocated buffers (Rule of 16). The spatial hash is central to the
simulation's ability to model emergent ecological phenomena with deterministic reproducibility
and scientific rigour.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import TypeVar, cast

C = TypeVar("C")


# ---------------------------------------------------------------------------
# Dataclass-based generic component storage
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class Entity:
    """Lightweight wrapper holding an entity id and attached components."""

    entity_id: int
    _components: dict[type[object], object] = field(default_factory=dict, repr=False)

    def add_component(self, component: object) -> None:
        """Attach a component instance keyed by its type.

        Args:
            component: Component instance to attach.
        """
        self._components[type(component)] = component

    def get_component(self, component_type: type[C]) -> C:
        """Return attached component of the given type.

        Args:
            component_type: The component class/type to retrieve.

        Returns:
            The component instance for the entity.
        """
        return cast(C, self._components[component_type])

    def has_component(self, component_type: type[object]) -> bool:
        """Return True if the entity has a component of the given type.

        Args:
            component_type: Component class/type to check for.

        Returns:
            bool: True if present, False otherwise.
        """
        return component_type in self._components

    def remove_component(self, component_type: type[object]) -> None:
        """Detach a component of the given type (no-op if absent).

        Args:
            component_type: Component class/type to remove.
        """
        self._components.pop(component_type, None)


# ---------------------------------------------------------------------------
# ECS World
# ---------------------------------------------------------------------------


class ECSWorld:
    """Central ECS registry managing entities, components and spatial hash.

    The world provides helpers for entity lifecycle, component indexing and
    a spatial hash grid for efficient cell membership queries.
    """

    def __init__(self) -> None:
        """Initialise the ECS world and its internal indices.

        Attributes initialized:
            _next_id: Next entity id to allocate.
            _entities: Mapping of entity id to Entity.
            _component_index: Index mapping component types to entity id sets.
            _spatial_hash: Grid cell roster mapping (x, y) to entity id sets.
        """
        self._next_id: int = 0
        self._entities: dict[int, Entity] = {}
        # component_type -> set of entity ids
        self._component_index: dict[type[object], set[int]] = defaultdict(set)
        # (x, y) -> set of entity ids (Spatial Hash / Grid Cell Roster)
        self._spatial_hash: dict[tuple[int, int], set[int]] = defaultdict(set)

    # ------------------------------------------------------------------
    # Entity lifecycle
    # ------------------------------------------------------------------

    def create_entity(self) -> Entity:
        """Allocate and register a new entity.

        Returns:
            Entity: Newly created entity object.
        """
        eid = self._next_id
        self._next_id += 1
        entity = Entity(entity_id=eid)
        self._entities[eid] = entity
        return entity

    def destroy_entity(self, entity_id: int) -> None:
        """Remove an entity and clean up index and spatial hash references.

        Args:
            entity_id: Identifier of the entity to destroy.
        """
        entity = self._entities.pop(entity_id, None)
        if entity is None:
            return
        # Clean component index
        for ctype in list(entity._components.keys()):
            self._component_index[ctype].discard(entity_id)
        # Clean spatial hash (search all cells – acceptable for sparse grids)
        for cell_set in self._spatial_hash.values():
            cell_set.discard(entity_id)

    def has_entity(self, entity_id: int) -> bool:
        """Return True if the entity exists.

        Args:
            entity_id: Entity identifier.

        Returns:
            bool: True if present.
        """
        return entity_id in self._entities

    def get_entity(self, entity_id: int) -> Entity:
        """Return the entity instance for the given id.

        Args:
            entity_id: Entity identifier.

        Returns:
            Entity: Matching entity.
        """
        return self._entities[entity_id]

    # ------------------------------------------------------------------
    # Component helpers
    # ------------------------------------------------------------------

    def add_component(self, entity_id: int, component: object) -> None:
        """Attach a component to an entity and update the component index.

        Args:
            entity_id: Target entity id.
            component: Component instance to attach.
        """
        entity = self._entities[entity_id]
        entity.add_component(component)
        self._component_index[type(component)].add(entity_id)

    def remove_component(self, entity_id: int, component_type: type[object]) -> None:
        """Detach a component of the specified type from an entity.

        Args:
            entity_id: Target entity id.
            component_type: Component class/type to remove.
        """
        entity = self._entities[entity_id]
        entity.remove_component(component_type)
        self._component_index[component_type].discard(entity_id)

    def query(self, *component_types: type[object]) -> Iterator[Entity]:
        """Yield all entities that possess all listed component types.

        Args:
            *component_types: Component classes/types to require.

        Yields:
            Entity: Entities matching the component set.
        """
        if not component_types:
            yield from self._entities.values()
            return
        # Start from the smallest set for efficiency
        sets = [self._component_index.get(ct, set()) for ct in component_types]
        smallest = min(sets, key=len)
        for eid in list(smallest):
            entity = self._entities.get(eid)
            if entity is None:
                continue
            if all(entity.has_component(ct) for ct in component_types):
                yield entity

    # ------------------------------------------------------------------
    # Spatial Hash
    # ------------------------------------------------------------------

    def register_position(self, entity_id: int, x: int, y: int) -> None:
        """Register an entity at grid cell (x, y).

        Args:
            entity_id: Entity identifier.
            x: X coordinate of the cell.
            y: Y coordinate of the cell.
        """
        self._spatial_hash[(x, y)].add(entity_id)

    def unregister_position(self, entity_id: int, x: int, y: int) -> None:
        """Remove an entity from a grid cell.

        Args:
            entity_id: Entity identifier.
            x: X coordinate of the cell.
            y: Y coordinate of the cell.
        """
        cell = self._spatial_hash.get((x, y))
        if cell is not None:
            cell.discard(entity_id)

    def move_entity(self, entity_id: int, old_x: int, old_y: int, new_x: int, new_y: int) -> None:
        """Atomically update spatial hash when an entity moves.

        Args:
            entity_id: Entity identifier.
            old_x: Previous X coordinate.
            old_y: Previous Y coordinate.
            new_x: New X coordinate.
            new_y: New Y coordinate.
        """
        self.unregister_position(entity_id, old_x, old_y)
        self.register_position(entity_id, new_x, new_y)

    def entities_at(self, x: int, y: int) -> set[int]:
        """Return the set of entity ids occupying a cell.

        Args:
            x: X coordinate.
            y: Y coordinate.

        Returns:
            set[int]: Entity ids occupying the cell.
        """
        return self._spatial_hash.get((x, y), set())

    # ------------------------------------------------------------------
    # Garbage collection
    # ------------------------------------------------------------------

    def collect_garbage(self, dead_entity_ids: list[int]) -> None:
        """Bulk destroy a list of dead entities.

        Args:
            dead_entity_ids: List of entity ids to remove.
        """
        for eid in dead_entity_ids:
            self.destroy_entity(eid)
