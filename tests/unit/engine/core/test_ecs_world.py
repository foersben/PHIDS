# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Unit tests for the PHIDS Entity-Component-System registry and spatial hash invariants.

This module validates the core data-structural invariants of :class:`~phids.engine.core.ecs.ECSWorld`:
correct entity lifecycle management (creation, destruction, component attachment and removal),
component index consistency under entity garbage collection, and the O(1) spatial hash operations
(``register_position``, ``move_entity``, ``entities_at``, ``unregister_position``) that underpin
all locality-based ecological interactions in the PHIDS engine. The hypothesis under test is that
the spatial hash provides strictly consistent membership semantics - an entity registered at
coordinates (x, y) must appear in ``entities_at(x, y)`` and must not appear at any other
coordinate, and must be absent from all cells after garbage collection removes it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from phids.engine.core.ecs import ECSWorld


class Marker:
    """Minimal test component used to verify ECS component attachment and type-based indexing.

    ``Marker`` carries a single integer payload so that test assertions can verify that the
    correct component instance is retrieved after attachment, without depending on any production
    component type.

    Attributes:
        value: Integer payload for assertion equality checks.
    """

    def __init__(self, value: int) -> None:
        """Initialise the Marker with the given integer payload.

        Args:
            value: Integer payload stored for subsequent assertion comparison.
        """
        self.value = value


def test_spatial_hash_register_move_and_gc(empty_world: ECSWorld) -> None:
    """Verifies that register_position, move_entity, and collect_garbage maintain consistent spatial hash membership.

    The invariant under test is that the spatial hash provides strict bijective location tracking:
    an entity appears in exactly one cell set at a time, is absent from its previous cell after
    ``move_entity``, and is absent from all cells after ``collect_garbage``. This consistency is
    required for O(1) co-location queries in the interaction and signaling phases to remain
    correct throughout the entity lifecycle.
    """
    world = empty_world
    entity = world.create_entity()
    world.add_component(entity.entity_id, Marker(1))

    world.register_position(entity.entity_id, 1, 2)
    assert entity.entity_id in world.entities_at(1, 2)

    world.move_entity(entity.entity_id, 1, 2, 3, 4)
    assert entity.entity_id not in world.entities_at(1, 2)
    assert entity.entity_id in world.entities_at(3, 4)

    world.collect_garbage([entity.entity_id])
    assert not world.has_entity(entity.entity_id)
    assert entity.entity_id not in world.entities_at(3, 4)


def test_register_position_replaces_previous_cell_membership(empty_world: ECSWorld) -> None:
    """Registering a new position moves membership to the new cell and clears the old roster."""
    world = empty_world
    entity = world.create_entity()

    world.register_position(entity.entity_id, 1, 1)
    world.register_position(entity.entity_id, 2, 2)

    assert entity.entity_id not in world.entities_at(1, 1)
    assert entity.entity_id in world.entities_at(2, 2)


def test_destroy_entity_cleans_spatial_hash_without_full_scan(empty_world: ECSWorld) -> None:
    """Destroying a registered entity removes it from the spatial hash and prunes empty cells."""
    world = empty_world
    entity = world.create_entity()

    world.register_position(entity.entity_id, 5, 7)
    world.destroy_entity(entity.entity_id)

    assert entity.entity_id not in world.entities_at(5, 7)
    assert (5, 7) not in world._spatial_hash


class OtherMarker:
    """Alternative test component for verifying multi-component ECS queries."""

    def __init__(self, value: int) -> None:
        """Initialise OtherMarker with integer payload."""
        self.value = value


def test_ecs_query_multi_component(empty_world: ECSWorld) -> None:
    """Verifies that query() accurately matches entities possessing multiple components."""
    world = empty_world
    e1 = world.create_entity()
    e2 = world.create_entity()
    e3 = world.create_entity()

    world.add_component(e1.entity_id, Marker(1))
    world.add_component(e2.entity_id, Marker(2))
    world.add_component(e2.entity_id, OtherMarker(20))
    world.add_component(e3.entity_id, OtherMarker(30))

    res = world.query(Marker, OtherMarker)
    assert len(res) == 1
    assert res[0].entity_id == e2.entity_id


def test_ecs_query_empty_args_returns_all(empty_world: ECSWorld) -> None:
    """Verifies that query() without args returns all living entities."""
    world = empty_world
    e1 = world.create_entity()
    e2 = world.create_entity()

    res = world.query()
    assert len(res) == 2
    ids = {e.entity_id for e in res}
    assert ids == {e1.entity_id, e2.entity_id}


def test_ecs_query_missing_component_returns_empty(empty_world: ECSWorld) -> None:
    """Verifies that querying for a component type no entity possesses returns empty."""
    world = empty_world
    e1 = world.create_entity()
    world.add_component(e1.entity_id, Marker(1))

    res = world.query(OtherMarker)
    assert res == []


def test_ecs_remove_component(empty_world: ECSWorld) -> None:
    """Verifies that removing a component updates the entity and the index."""
    world = empty_world
    e1 = world.create_entity()
    world.add_component(e1.entity_id, Marker(1))

    assert len(world.query(Marker)) == 1
    world.remove_component(e1.entity_id, Marker)
    assert len(world.query(Marker)) == 0
    assert not e1.has_component(Marker)


def test_ecs_unregister_position_guard(empty_world: ECSWorld) -> None:
    """Verifies that unregister_position correctly manages the reverse position index."""
    world = empty_world
    e1 = world.create_entity()

    world.register_position(e1.entity_id, 1, 1)

    # Try unregistering from a position the entity is not currently associated with
    world.unregister_position(e1.entity_id, 2, 2)
    # The reverse index should remain intact because it didn't match (2,2)
    assert world._entity_positions.get(e1.entity_id) == (1, 1)

    # Now legitimately unregister
    world.unregister_position(e1.entity_id, 1, 1)
    assert e1.entity_id not in world._entity_positions
