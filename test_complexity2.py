def _apply_toxin_lethality(swarm, toxin_val, lethality_rate):
    casualties = int(lethality_rate * toxin_val * swarm.population)
    if casualties > 0:
        swarm.population = max(0, swarm.population - casualties)
        energy_loss = casualties * swarm.energy_min
        swarm.energy = max(0.0, swarm.energy - energy_loss)


def _apply_toxin_to_swarms(
    sub_id: int,
    lethal: bool,
    lethality_rate: float,
    repellent: bool,
    repellent_walk_ticks: int,
    env,
    world,
) -> None:
    dead_swarms: list[int] = []

    for entity in world.query():
        swarm = entity.get_component()
        toxin_val = float(env.toxin_layers[sub_id, swarm.x, swarm.y])
        if toxin_val <= 0.0:
            continue

        if lethal and lethality_rate > 0.0:
            _apply_toxin_lethality(swarm, toxin_val, lethality_rate)

        if repellent and not swarm.repelled:
            swarm.repelled = True
            swarm.repelled_ticks_remaining = repellent_walk_ticks

        if swarm.population <= 0:
            world.unregister_position(entity.entity_id, swarm.x, swarm.y)
            dead_swarms.append(entity.entity_id)

    if dead_swarms:
        world.collect_garbage(dead_swarms)
