# Signaling and Substance Lifecycle

The signaling system is the most chemically expressive part of PHIDS. It is responsible for turning
local ecological triggers into runtime substance entities, environmental emissions, mycorrhizal
relays, and toxin effects.

This chapter documents the current implementation in `src/phids/engine/systems/signaling.py` and
its associated runtime data structures.

## Role in the Engine

`run_signaling()` executes after lifecycle and interaction have already updated plant and swarm
state for the current tick. It therefore observes the post-feeding, post-movement ecological
configuration of the world.

Its high-level responsibilities are:

- evaluate trigger conditions,
- create and update `SubstanceComponent` entities,
- advance synthesis timers,
- activate substances,
- emit signals and toxins,
- relay signals through mycorrhizal links,
- manage aftereffects and deactivation,
- delegate diffusion to `GridEnvironment`.

## Runtime Data Model

The key runtime record is `SubstanceComponent`, which stores:

- the owning plant ID,
- the target signal or toxin layer index,
- whether the substance is a toxin,
- synthesis duration and remaining synthesis time,
- active state,
- configured and remaining aftereffect,
- lethality and repellence parameters,
- optional activation-condition trees,
- energy cost per tick,
- the `triggered_this_tick` flag.

This means substances are represented as discrete runtime entities rather than as anonymous field
values.

## Trigger Evaluation Model

At the beginning of each signaling pass, the system:

- clears local toxin state in the environment,
- resets `triggered_this_tick` on all substance entities,
- iterates over plants,
- evaluates configured trigger rules for that plant species.

The current base trigger test is co-located predator population at the plant’s cell, aggregated via
`world.entities_at(x, y)`.

This is important: trigger evaluation is locality-based and spatial-hash-backed.

## Activation Conditions

Beyond the base predator-threshold trigger, the current runtime supports nested activation-condition
trees.

Implemented node kinds include:

- `enemy_presence`
- `substance_active`
- `all_of`
- `any_of`

This allows the runtime to express richer conditions than a simple one-cell matrix lookup.

## Substance Materialization

When a trigger fires for a `(plant, substance_id)` pair and no matching runtime substance entity
exists, `run_signaling()` creates a new `SubstanceComponent`.

The created runtime entity receives its behavior parameters from the triggering schema, including:

- toxin/signal classification,
- synthesis duration,
- lethality and repellence settings,
- aftereffect duration,
- activation condition,
- energy cost.

This means trigger schemas are not merely booleans; they are substance-instantiation templates.

## Synthesis and Activation

After trigger evaluation, the system advances synthesis for substances that were triggered this tick
but are not yet active.

Current behavior:

- `synthesis_remaining` is decremented while the trigger is satisfied,
- once the timer reaches zero, the activation-condition tree is checked,
- if the activation condition passes, the substance becomes active,
- `aftereffect_remaining_ticks` is initialized from `aftereffect_ticks`.

This yields a current-state substance lifecycle with at least three phases:

1. materialized but inactive,
2. synthesizing,
3. active.

## Emission Model

Active substances then emit into the environment.

### Signals

For non-toxin substances:

- the signal layer at the owner plant’s cell is incremented,
- the signal may also be relayed through mycorrhizal connections,
- airborne diffusion is delegated to `env.diffuse_signals()` later in the pass.

### Toxins

For toxin substances:

- the toxin layer at the owner plant’s cell is incremented,
- toxin effects may be applied to swarms directly through `_apply_toxin_to_swarms()`,
- toxin diffusion is still delegated to `env.diffuse_toxins()` in the current implementation.

This is one of the most important current-state nuances of PHIDS: toxins are conceptually local in
parts of the signaling design, but in the present runtime they still interact with toxin layers and
pass through the toxin diffusion helper.

## Energy Maintenance Cost

When a substance is active and `energy_cost_per_tick > 0.0`, the owner plant loses energy each
active tick.

This cost is immediately written back into the environment’s plant-energy buffers via
`env.set_plant_energy(...)`.

## Mycorrhizal Relay

Signals may be relayed via `_relay_signal_via_mycorrhizal(...)` to connected plants.

Current relay properties:

- relay follows plant mycorrhizal connections,
- inter-species relay can be disabled,
- deposited amount is attenuated by `signal_velocity`,
- relay bypasses airborne transport by depositing directly into signal layers at connected cells.

This makes root networks a distinct signaling pathway rather than just another diffusion effect.

## Deactivation and Aftereffects

After active substances have emitted, the system evaluates persistence.

### Signals

If a signal was not triggered this tick:

- its remaining aftereffect is decremented,
- once the remaining aftereffect reaches zero, the substance becomes inactive.

### Toxins

If a toxin was not triggered this tick:

- it is deactivated immediately in the current implementation,
- its cell-local toxin layer value is zeroed at the owner plant’s position.

Thus signals and toxins currently follow different persistence semantics.

## Diffusion Delegation

At the end of `run_signaling()`, the system calls:

- `env.diffuse_signals()`
- `env.diffuse_toxins()`

This means that final field propagation is delegated to the environmental layer subsystem rather than
implemented inline in the signaling system.

## Direct Toxin Effects

The signaling module also contains `_apply_toxin_to_swarms(...)`, which currently:

- reads toxin concentration at swarm positions,
- applies lethal population loss when configured,
- toggles repelled state and repelled-walk duration when configured.

This coexists with toxin-based casualty handling in the interaction phase, which is an important
current-state coupling to keep documented accurately.

## Evidence from Tests

The current test suite verifies several important signaling behaviors.

### Configured toxin materialization

Tests verify that a trigger can spawn a toxin with configured lethal and repellent properties.

### Co-located population aggregation

Trigger thresholds are tested against the aggregate population of multiple co-located swarms of the
same predator species.

### Immediate toxin deactivation

Tests verify that toxins deactivate when the triggering species is gone and aftereffect is zero.

### Signal aftereffect persistence

Tests verify that signals can remain active for a bounded number of ticks after the triggering swarm
is removed.

### Non-reactivation without trigger

Tests verify that an inactive substance does not spontaneously reactivate without renewed triggering.

### Precursor and composite gates

Tests verify:

- `substance_active` gating,
- `all_of` composite conditions,
- `any_of` composite conditions.

### Mycorrhizal relay context

The runtime design of `run_signaling()` includes mycorrhizal signal relay as a distinct route for
communication across plants.

## Methodological Limits of the Current Signaling Model

The current implementation should be described precisely.

- toxins are rebuilt locally per signaling pass, yet still pass through `env.diffuse_toxins()`,
- toxin effects exist both in the signaling module and in the interaction module,
- synthesis delay and signal aftereffect are explicit,
- toxin persistence and signal persistence are not symmetric,
- activation conditions are powerful but still expressed as JSON-like predicate trees rather than a
  separate compiled rule engine.

These are key facts about the current system state.

## Verified Current-State Evidence

- `src/phids/engine/systems/signaling.py`
- `src/phids/engine/components/substances.py`
- `src/phids/api/schemas.py`
- `tests/test_systems_behavior.py`

## Where to Read Next

- For the field layer used by signal and toxin emission: [`biotope-and-double-buffering.md`](biotope-and-double-buffering.md)
- For the engine-wide phase ordering: [`index.md`](index.md)
- For scenario-side trigger and substance definitions: [`../scenarios/schema-and-curated-examples.md`](../scenarios/schema-and-curated-examples.md)
