"""Entity-Component-System (ECS) registry with O(1) spatial hash support.

The ECS maintains:
* A flat entity registry keyed by integer entity id.
* A per-component-type index for fast query.
* A Spatial Hash (Grid Cell Roster) enabling O(1) cell-membership lookup.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any, TypeVar

C = TypeVar("C")


# ---------------------------------------------------------------------------
# Dataclass-based generic component storage
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class Entity:
    """Lightweight wrapper holding an entity id and its attached components."""

    entity_id: int
    _components: dict[type[Any], Any] = field(default_factory=dict, repr=False)

    def add_component(self, component: Any) -> None:
        """Attach a component instance (keyed by its type)."""
        self._components[type(component)] = component

    def get_component(self, component_type: type[C]) -> C:
        """Return attached component of *component_type* or raise KeyError."""
        return self._components[component_type]  # type: ignore[return-value]

    def has_component(self, component_type: type[Any]) -> bool:
        """Return True if the entity has a component of *component_type*."""
        return component_type in self._components

    def remove_component(self, component_type: type[Any]) -> None:
        """Detach a component (no-op if absent)."""
        self._components.pop(component_type, None)


# ---------------------------------------------------------------------------
# ECS World
# ---------------------------------------------------------------------------


class ECSWorld:
    """Central ECS registry.

    Responsibilities
    ----------------
    * Entity lifecycle: create / destroy.
    * Component index: fast iteration over all entities sharing a component.
    * Spatial Hash Grid: O(1) lookup of entities occupying a cell (x, y).
    """

    def __init__(self) -> None:
        self._next_id: int = 0
        self._entities: dict[int, Entity] = {}
        # component_type -> set of entity ids
        self._component_index: dict[type[Any], set[int]] = defaultdict(set)
        # (x, y) -> set of entity ids (Spatial Hash / Grid Cell Roster)
        self._spatial_hash: dict[tuple[int, int], set[int]] = defaultdict(set)

    # ------------------------------------------------------------------
    # Entity lifecycle
    # ------------------------------------------------------------------

    def create_entity(self) -> Entity:
        """Allocate and register a new entity, returning it."""
        eid = self._next_id
        self._next_id += 1
        entity = Entity(entity_id=eid)
        self._entities[eid] = entity
        return entity

    def destroy_entity(self, entity_id: int) -> None:
        """Remove an entity and all component index / spatial hash references."""
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
        """Return True if the entity exists."""
        return entity_id in self._entities

    def get_entity(self, entity_id: int) -> Entity:
        """Return entity by id or raise KeyError."""
        return self._entities[entity_id]

    # ------------------------------------------------------------------
    # Component helpers
    # ------------------------------------------------------------------

    def add_component(self, entity_id: int, component: Any) -> None:
        """Attach *component* to entity *entity_id* and update the index."""
        entity = self._entities[entity_id]
        entity.add_component(component)
        self._component_index[type(component)].add(entity_id)

    def remove_component(self, entity_id: int, component_type: type[Any]) -> None:
        """Detach component of *component_type* from entity *entity_id*."""
        entity = self._entities[entity_id]
        entity.remove_component(component_type)
        self._component_index[component_type].discard(entity_id)

    def query(self, *component_types: type[Any]) -> Iterator[Entity]:
        """Yield all entities that possess *all* listed component types."""
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
        """Register an entity at grid cell (x, y)."""
        self._spatial_hash[(x, y)].add(entity_id)

    def unregister_position(self, entity_id: int, x: int, y: int) -> None:
        """Remove an entity from grid cell (x, y)."""
        cell = self._spatial_hash.get((x, y))
        if cell is not None:
            cell.discard(entity_id)

    def move_entity(self, entity_id: int, old_x: int, old_y: int, new_x: int, new_y: int) -> None:
        """Atomically update spatial hash when entity moves."""
        self.unregister_position(entity_id, old_x, old_y)
        self.register_position(entity_id, new_x, new_y)

    def entities_at(self, x: int, y: int) -> set[int]:
        """Return the set of entity ids occupying cell (x, y) – O(1)."""
        return self._spatial_hash.get((x, y), set())

    # ------------------------------------------------------------------
    # Garbage collection
    # ------------------------------------------------------------------

    def collect_garbage(self, dead_entity_ids: list[int]) -> None:
        """Bulk destroy a list of dead entities."""
        for eid in dead_entity_ids:
            self.destroy_entity(eid)
