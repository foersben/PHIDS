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
- garbage-collect orphaned substance entities before evaluation,
- create and update `SubstanceComponent` entities,
- advance synthesis timers,
- activate substances,
- emit signals and toxins,
- relay signals through mycorrhizal links,
- manage aftereffects and deactivation,
- delegate airborne signal diffusion to `GridEnvironment`.

## Runtime Data Model

The key runtime record is `SubstanceComponent`, which stores:

- the owning plant ID,
- the target signal or toxin layer index,
- whether the substance is a toxin,
- synthesis duration and remaining synthesis time,
- active state,
- configured and remaining aftereffect,
- irreversible activation mode,
- lethality and repellence parameters,
- optional activation-condition trees,
- energy cost per tick,
- the `triggered_this_tick` flag.

This means substances are represented as discrete runtime entities rather than as anonymous field
values.

## Trigger Evaluation Model

At the beginning of each signaling pass, the system:

- removes orphaned substance entities whose owner plant no longer exists,
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

- `enemy_presence` — evaluates aggregate co-located population of a specific predator species,
- `substance_active` — checks whether a named substance on the same plant is currently active,
- `environmental_signal` — checks whether a named signal layer exceeds a minimum concentration at
  the plant's cell, enabling defenses to activate in response to ambient alarm signals deposited by
  mycorrhizal relay or airborne diffusion from neighbours,
- `all_of` — short-circuit conjunction of child predicates,
- `any_of` — short-circuit disjunction of child predicates.

This allows the runtime to express richer conditions than a simple one-cell matrix lookup.

The `environmental_signal` predicate is particularly significant: it provides a direct pathway by
which mycorrhizally relayed or airborne signal concentrations can satisfy an activation condition,
enabling a form of primed systemic defense in neighbouring plants. However, relay deposits signal
concentration at connected plant cells without directly firing their trigger rules — a receiving
plant must have a trigger rule configured with an `environmental_signal` activation condition to
act on the relayed concentration.

## Substance Materialization

When a trigger fires for a `(plant, substance_id)` pair and no matching runtime substance entity
exists, `run_signaling()` creates a new `SubstanceComponent`.

The created runtime entity receives its behavior parameters from the triggering schema, including:

- toxin/signal classification,
- synthesis duration,
- lethality and repellence settings,
- aftereffect duration,
- irreversible activation flag,
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
- toxin effects are applied to swarms directly through `_apply_toxin_to_swarms()`,
- toxin damage is resolved once per active toxin layer per tick,
- toxins do not diffuse through the environment.

This is one of the most important current-state nuances of PHIDS: toxin layers are rebuilt locally
from active emitters each pass and therefore behave as plant-tissue defenses rather than airborne
chemical clouds.

## Energy Maintenance Cost

When a substance is active and `energy_cost_per_tick > 0.0`, the owner plant loses energy each
active tick.

This cost is immediately written back into the environment’s plant-energy buffers via
`env.set_plant_energy(...)`.

Current self-preservation semantics are asymmetric by design. If a substance is only lingering due to
aftereffect persistence and paying the next maintenance tick would push the plant below its
`survival_threshold`, the substance is deactivated instead of draining the plant. By contrast, if the
defense is still actively triggered—or is irreversible—the plant may continue paying the energetic
cost and die from defense maintenance. That behavior is currently treated as an intentional ecological
trade-off rather than as an engine bug.

## Mycorrhizal Relay

Signals may be relayed via `_relay_signal_via_mycorrhizal(...)` to connected plants.

Current relay properties:

- relay follows plant mycorrhizal connections,
- inter-species relay can be disabled,
- deposited amount is attenuated by `signal_velocity`,
- relay bypasses airborne transport by depositing directly into signal layers at connected cells.

This makes root networks a distinct signaling pathway rather than just another diffusion effect.

However, the current runtime should not be over-interpreted as a full systemic alarm cascade. The
relay deposits signal concentration into neighbouring cells, but because trigger predicates do not yet
query ambient signal concentration, the relay does not automatically cause neighbouring plants to
synthesize their own defenses.

## Deactivation and Aftereffects

After active substances have emitted, the system evaluates persistence.

### Signals

If a signal was not triggered this tick:

- its remaining aftereffect is decremented,
- once the remaining aftereffect reaches zero, the substance becomes inactive.

### Toxins

Toxins now follow the same aftereffect persistence model as signals.

If a toxin was not triggered this tick:

- `aftereffect_remaining_ticks` is decremented,
- once it reaches zero, the toxin deactivates.

### Irreversible induced defense mode

When `irreversible=True`, an active substance is pinned in the triggered state and does not
deactivate due to trigger loss or aftereffect expiry. This models a SAR-like permanent induced
defense response.

## Diffusion Delegation

At the end of `run_signaling()`, the system calls:

- `env.diffuse_signals()`

This means that airborne signal propagation is delegated to the environmental layer subsystem rather
than implemented inline in the signaling system. Toxins are intentionally excluded from diffusion.

## Direct Toxin Effects

The signaling module contains `_apply_toxin_to_swarms(...)`, which currently:

- reads toxin concentration at each swarm's current cell,
- applies lethal population loss when `sub.lethal` is set and `lethality_rate > 0`,
- toggles the `repelled` flag and initializes `repelled_ticks_remaining` when `sub.repellent` is set.

This is the sole runtime authority for toxin damage and repellence.

### Immediate garbage collection of toxin-killed swarms

Critically, after lethal casualties are applied, `_apply_toxin_to_swarms` immediately evaluates
whether `swarm.population <= 0`. If so, the swarm is subjected to in-place localised garbage
collection within the signaling phase:

1. `world.unregister_position(entity_id, x, y)` removes the entity from the spatial hash
   before the loop completes,
2. the entity ID is appended to a `dead_swarms` list,
3. after the full swarm iteration, `world.collect_garbage(dead_swarms)` destroys all queued
   entities in a single bulk pass.

Without this immediate GC step, a swarm annihilated by chemical defense would persist as a ghost
entry in the spatial hash until the subsequent tick's interaction phase performed its own death
sweep. Such ghost entries corrupt O(1) spatial-hash lookups and confound the `enemy_presence`
predicate in `_check_activation_condition`, which could cause a plant to maintain a defensive
posture against a predator population that has already been eliminated.

## Evidence from Tests

The current test suite verifies several important signaling behaviors.

### Configured toxin materialization

Tests verify that a trigger can spawn a toxin with configured lethal and repellent properties.

### Co-located population aggregation

Trigger thresholds are tested against the aggregate population of multiple co-located swarms of the
same predator species.

### Toxin persistence controls

Tests verify that:

- toxins with nonzero aftereffect linger after trigger loss,
- toxins with zero aftereffect stop on the next non-triggered tick,
- irreversible toxins remain active after trigger loss,
- ownerless substance entities are garbage-collected before they can accumulate as leaks,
- multiple emitters of the same toxin layer do not multiply per-tick damage.

### Immediate GC of toxin-killed swarms

Tests verify that a swarm whose population reaches zero through lethal toxin damage is absent from
both the ECS entity registry and the spatial hash immediately after `run_signaling` completes,
without requiring a subsequent interaction tick to perform cleanup.

### Signal aftereffect persistence

Tests verify that signals can remain active for a bounded number of ticks after the triggering swarm
is removed.

### Defense-maintenance death attribution

Tests also verify that non-triggered aftereffects do not continue draining a plant below its survival
threshold once predator pressure is gone. When plants do die from active defense maintenance, the
telemetry layer now attributes that event explicitly.

### Non-reactivation without trigger

Tests verify that an inactive substance does not spontaneously reactivate without renewed triggering.

### Precursor and composite gates

Tests verify:

- `substance_active` gating,
- `all_of` composite conditions,
- `any_of` composite conditions,
- `environmental_signal` threshold gating.

### Mycorrhizal relay context

The runtime design of `run_signaling()` includes mycorrhizal signal relay as a distinct route for
communication across plants.

## Methodological Limits of the Current Signaling Model

The current implementation should be described precisely.

- toxins are rebuilt locally per signaling pass and never diffuse,
- toxin effects are applied only in the signaling module,
- synthesis delay and signal aftereffect are explicit,
- irreversible mode intentionally allows always-on defenses once activated,
- mycorrhizal relay does not presently constitute a direct ambient-signal trigger pathway,
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
