"""Experimental validation suite for test ecs world.

This module defines hypothesis-driven checks for deterministic ecosystem behavior, API constraints, and simulation invariants. The tests map computational rules to biological interpretations, including metabolic attrition, trigger-gated signaling, and O(1) spatial locality assumptions, to ensure that implementation details remain aligned with the PHIDS scientific model.
"""

from __future__ import annotations

from phids.engine.core.ecs import ECSWorld


class Marker:
    """Represent Marker state used by PHIDS components and tests.

    The class encapsulates structured state required for deterministic interactions in ECS or test scaffolding contexts.

    """

    def __init__(self, value: int) -> None:
        """Execute init for Marker within the PHIDS processing pipeline.

        The implementation preserves deterministic control flow and maintains consistency with ECS-oriented state management.

        Args:
            value: Input value used to parameterize deterministic behavior for this callable.

        Returns:
            None. Object state is initialized for subsequent deterministic operations.

        """
        self.value = value


def test_spatial_hash_register_move_and_gc() -> None:
    """Validates the spatial hash register move and gc invariant and confirms the expected biological behavior under controlled simulation conditions.

    The assertions in this test enforce deterministic state transitions so ecological outcomes remain consistent with configured constraints and signal-response dynamics.

    Returns:
        None. The function verifies invariant compliance through assertions rather than data return.

    """
    world = ECSWorld()
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
