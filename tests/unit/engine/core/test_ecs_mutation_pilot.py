# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Focused pilot tests for ECSWorld methods targeted by mutmut."""

from __future__ import annotations

import pytest

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


def test_ecs_world_structural_version() -> None:
    """Validate ECSWorld structural version increments accurately."""
    world = ECSWorld()
    v0 = world._structural_version

    e1 = world.create_entity()
    v1 = world._structural_version
    assert v1 == v0 + 1, "Creating an entity should increment version by exactly 1"

    comp = PlantComponent(e1.entity_id, 0, 5, 5, 10.0, 10.0, 10.0, 0.1, 1.0, 5, 1.0, 3.0, 1.0)
    world.add_component(e1.entity_id, comp)
    v2 = world._structural_version
    assert v2 == v1 + 1, "Adding a component should increment version by exactly 1"

    world.remove_component(e1.entity_id, PlantComponent)
    v3 = world._structural_version
    assert v3 == v2 + 1, "Removing a component should increment version by exactly 1"

    world.destroy_entity(e1.entity_id)
    v4 = world._structural_version
    assert v4 == v3 + 1, "Destroying an entity should increment version by exactly 1"


def test_ecs_world_initial_structural_version():
    """Verify that a newly instantiated ECSWorld has a _structural_version of exactly 0.

    This explicitly kills mutmut mutant 10, which mutates:
    - self._structural_version: int = 0
    + self._structural_version: int = 1
    """
    world = ECSWorld()
    assert world._structural_version == 0, "Initial structural version must be exactly 0"


def test_ecs_entity_remove_component_pop_returns_default():
    """Verify that removing a non-existent component does not raise a KeyError.

    This explicitly kills mutmut mutant 3, which mutates:
    - self._components.pop(component_type, None)
    + self._components.pop(component_type, )
    """
    from phids.engine.core.ecs import Entity

    class FakeComp:
        pass

    e = Entity(1)
    e._components[FakeComp] = FakeComp()
    e.remove_component(FakeComp)
    # the second argument to pop is missing if mutmut_3 survives. So if we pop a nonexistent one, it will raise KeyError
    # so we call it again on a missing component.
    # We'll assert that calling remove_component on a non-existent component does not raise KeyError.
    try:
        e.remove_component(FakeComp)
    except KeyError:
        pytest.fail("remove_component raised KeyError. It should pop with a default of None.")
