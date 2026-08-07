def _resolve_repulsion_or_gradient(
    swarm, env, diet_matrix, scratch_cx, scratch_cy, scratch_scores, scratch_adjusted, scratch_weights
):
    if swarm.repelled and swarm.repelled_ticks_remaining > 0:
        nx, ny = 0, 0
        swarm.repelled_ticks_remaining -= 1
        if swarm.repelled_ticks_remaining <= 0:
            swarm.repelled = False
        return nx, ny

    if True:  # _is_swarm_anchored mock
        return swarm.x, swarm.y
    return 1, 1


def _resolve_swarm_movement(
    swarm,
    entity,
    env,
    world,
    diet_matrix,
    tile_populations,
    scratch_cx,
    scratch_cy,
    scratch_scores,
    scratch_adjusted,
    scratch_weights,
):
    if swarm.move_cooldown > 0:
        swarm.move_cooldown -= 1
        return False

    if getattr(swarm, "aversion_memory", 0.0) > 0.0:
        swarm.aversion_memory *= 0.95
        if swarm.aversion_memory < 0.01:
            swarm.aversion_memory = 0.0

    old_x, old_y = swarm.x, swarm.y

    if (
        not swarm.repelled
        and 0 <= swarm.x < env.width
        and 0 <= swarm.y < env.height
        and tile_populations[swarm.y * env.width + swarm.x] > 100
    ):
        swarm.repelled = True
        swarm.repelled_ticks_remaining = 1

    nx, ny = _resolve_repulsion_or_gradient(
        swarm, env, diet_matrix, scratch_cx, scratch_cy, scratch_scores, scratch_adjusted, scratch_weights
    )

    has_moved = False
    if (nx, ny) != (old_x, old_y):
        has_moved = True

    swarm.move_cooldown = swarm.velocity - 1
    return has_moved
