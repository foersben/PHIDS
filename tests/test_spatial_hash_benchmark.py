from __future__ import annotations

from phids.engine.core.ecs import ECSWorld


def test_spatial_hash_query_benchmark(benchmark) -> None:  # type: ignore[no-untyped-def]
    world = ECSWorld()

    for idx in range(2000):
        entity = world.create_entity()
        world.register_position(entity.entity_id, idx % 40, (idx // 40) % 40)

    def query_hot_cell() -> int:
        return len(world.entities_at(10, 10))

    count = benchmark(query_hot_cell)
    assert count >= 0
