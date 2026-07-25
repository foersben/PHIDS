# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Focused pilot tests for ECSWorld methods targeted by mutmut."""

from __future__ import annotations

from phids.engine.components.plant import PlantComponent
from phids.engine.core.ecs import ECSWorld, Entity


def test_ecs_entity_component_management() -> None:
    """Validate Entity component attachment and detachment."""
    entity = Entity(100)
    assert not entity.has_component(PlantComponent)

    comp = PlantComponent(100, 0, 5, 5, 10.0, 10.0, 10.0, 0.1, 1.0, 5, 1.0, 3.0, 1.0)
    entity.add_component(comp)

    assert entity.has_component(PlantComponent)
    assert entity.get_component(PlantComponent) is comp

    entity.remove_component(PlantComponent)
    assert not entity.has_component(PlantComponent)


def test_ecs_world_component_indexing() -> None:
    """Validate ECSWorld component-level indexes."""
    world = ECSWorld()
    e = world.create_entity()

    comp = PlantComponent(e.entity_id, 0, 5, 5, 10.0, 10.0, 10.0, 0.1, 1.0, 5, 1.0, 3.0, 1.0)
    world.add_component(e.entity_id, comp)

    entities = list(world.query(PlantComponent))
    assert len(entities) == 1
    assert entities[0] == e

    world.remove_component(e.entity_id, PlantComponent)
    entities = list(world.query(PlantComponent))
    assert len(entities) == 0


def test_ecs_world_entity_lifecycle() -> None:
    """Validate ECSWorld entity creation, lookup, and destruction."""
    world = ECSWorld()
    e1 = world.create_entity()

    assert world.has_entity(e1.entity_id)
    assert world.get_entity(e1.entity_id) is e1

    world.destroy_entity(e1.entity_id)
    assert not world.has_entity(e1.entity_id)

    # Reusing ids? ECSWorld just increments
    e2 = world.create_entity()
    assert e2.entity_id != e1.entity_id


def test_ecs_world_bulk_garbage_collection() -> None:
    """Validate deferred garbage collection of entities."""
    world = ECSWorld()
    e1 = world.create_entity()
    e2 = world.create_entity()

    assert world.has_entity(e1.entity_id)
    assert world.has_entity(e2.entity_id)

    world.collect_garbage([e1.entity_id, e2.entity_id])

    assert not world.has_entity(e1.entity_id)
    assert not world.has_entity(e2.entity_id)


def test_ecs_entity_id_monotonicity() -> None:
    """Verify that ECSWorld assigns strictly monotonic, unique IDs starting from 0."""
    world = ECSWorld()
    entities = [world.create_entity() for _ in range(5)]
    ids = [e.entity_id for e in entities]

    # Assert exact expected IDs to kill default offset mutations and assignment mutations
    assert ids == [0, 1, 2, 3, 4]

    # Destroying an entity should not affect the monotonically increasing counter
    world.destroy_entity(entities[2].entity_id)
    e_new = world.create_entity()
    assert e_new.entity_id == 5
