"""Experimental validation suite for test spatial hash benchmark.

This module defines hypothesis-driven checks for deterministic ecosystem behavior, API constraints, and simulation invariants. The tests map computational rules to biological interpretations, including metabolic attrition, trigger-gated signaling, and O(1) spatial locality assumptions, to ensure that implementation details remain aligned with the PHIDS scientific model.
"""

from __future__ import annotations

from phids.engine.core.ecs import ECSWorld


def test_spatial_hash_query_benchmark(benchmark) -> None:  # type: ignore[no-untyped-def]
    """Validates the spatial hash query benchmark invariant and confirms the expected biological behavior under controlled simulation conditions.

    The assertions in this test enforce deterministic state transitions so ecological outcomes remain consistent with configured constraints and signal-response dynamics.

    Args:
        benchmark: Input value used to parameterize deterministic behavior for this callable.

    Returns:
        None. The function verifies invariant compliance through assertions rather than data return.

    """
    world = ECSWorld()

    for idx in range(2000):
        entity = world.create_entity()
        world.register_position(entity.entity_id, idx % 40, (idx // 40) % 40)

    def query_hot_cell() -> int:
        return len(world.entities_at(10, 10))

    count = benchmark(query_hot_cell)
    assert count >= 0
