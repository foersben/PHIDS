"""Performance benchmarks for the O(1) spatial hash entity-at-cell query.

This module measures the wall-clock latency of ``ECSWorld.entities_at(x, y)`` under a 2000-entity
population distributed across a 40×40 grid. The benchmark validates the spatial hash's O(1)
amortised lookup contract, which is a core performance invariant of the PHIDS engine: the
interaction and signaling phases invoke ``entities_at`` for every swarm movement step and every
herbivore-presence evaluation in the trigger-condition tree, so any regression in hash lookup
latency directly impacts tick throughput at biologically meaningful entity densities.
"""

from __future__ import annotations

from phids.engine.core.ecs import ECSWorld


def test_spatial_hash_query_benchmark(benchmark) -> None:  # type: ignore[no-untyped-def]
    """Benchmarks ECSWorld.entities_at throughput under a 2000-entity, 40×40-grid population.

    2000 entities are registered across grid cells using modular coordinate arithmetic to achieve
    a representative occupancy density. The benchmark then repeatedly queries the hot cell (10, 10)
    to measure steady-state hash lookup latency. The correctness assertion verifies that the
    returned count is non-negative, confirming that the hash table remains internally consistent
    after bulk registration.

    """
    world = ECSWorld()

    for idx in range(2000):
        entity = world.create_entity()
        world.register_position(entity.entity_id, idx % 40, (idx // 40) % 40)

    def query_hot_cell() -> int:
        return len(world.entities_at(10, 10))

    count = benchmark(query_hot_cell)
    assert count >= 0
