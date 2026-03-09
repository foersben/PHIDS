from __future__ import annotations

from phytodynamics.engine.core.ecs import ECSWorld


class Marker:
    def __init__(self, value: int) -> None:
        self.value = value


def test_spatial_hash_register_move_and_gc() -> None:
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
