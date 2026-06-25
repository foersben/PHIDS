# Biotope and Double-Buffering

`GridEnvironment` is the canonical owner of PHIDS’s grid-aligned environmental state. It is where
continuous fields, diffusion behavior, wind transport, and the most explicit double-buffering
mechanics of the current engine are implemented.

This chapter documents the current implementation in `src/phids/engine/core/biotope.py`.

## Role in the Engine

`GridEnvironment` provides the field side of the hybrid ECS + cellular-automata runtime. While
`ECSWorld` stores discrete entities, `GridEnvironment` stores the continuous or grid-aggregated
quantities that those entities read from and write to.

In current implementation it owns:

- `plant_energy_layer`
- `_plant_energy_layer_write`
- `plant_energy_by_species`
- `_plant_energy_by_species_write`
- `signal_layers`
- `_signal_layers_write`
- `toxin_layers`
- `_toxin_layers_write`
- `wind_vector_x`
- `wind_vector_y`
- `flow_field`

## Architectural Significance

PHIDS’s design rules repeatedly refer to double-buffering. In the current codebase, that principle
is most concretely embodied in `GridEnvironment`.

This means `GridEnvironment` is not just a container for NumPy arrays. It is the subsystem that
makes the engine’s buffered environmental semantics real.

## Bounded Memory Discipline

The biotope enforces several hard constraints at initialization time:

- `1 <= width <= GRID_W_MAX`
- `1 <= height <= GRID_H_MAX`
- `1 <= num_signals <= MAX_SUBSTANCE_TYPES`
- `1 <= num_toxins <= MAX_SUBSTANCE_TYPES`

It also pre-allocates the species-specific plant-energy tensor with shape:

- `(MAX_FLORA_SPECIES, width, height)`

This is the environmental expression of the Rule of 16. The engine does not dynamically resize
these core buffers during a simulation tick.

## State Layout

### Aggregate plant-energy layer

`plant_energy_layer` is the read-visible aggregate plant-energy field consumed by later phases such
as flow-field generation.

### Per-species plant-energy tensor

`plant_energy_by_species` stores species-specific contributions, allowing the environment to retain
species granularity while also exposing an aggregate field.

### Signal and toxin layers

Signals and toxins are each stored as stacked layers of shape:

- `(num_signals, width, height)`
- `(num_toxins, width, height)`

This allows PHIDS to represent multiple airborne signals and multiple toxin fields in a vectorized
way.

### Wind fields

Wind is represented as two NumPy layers:

- `wind_vector_x`
- `wind_vector_y`

In the current implementation these are typically filled uniformly, but the abstraction also
supports per-cell updates.

### Flow field

`flow_field` is stored in the environment as a scalar guidance surface of shape `(width, height)`.
It is written by the flow-field phase and read by the interaction phase.

## Double-Buffering Mechanics

### Plant-energy writes

Plant-energy writes are not applied directly to the read-visible aggregate field.

Instead:

- species-specific writes go to `_plant_energy_by_species_write`,
- `rebuild_energy_layer()` aggregates those writes into `_plant_energy_layer_write`,
- read and write buffers are swapped,
- the write buffers are refreshed from the new read-visible values.

This is one of the clearest examples of PHIDS’s buffered-state discipline.

### Signal diffusion writes

Signal diffusion reads from `signal_layers`, writes into `_signal_layers_write`, and then swaps the
buffers.

### Toxin diffusion writes

Toxin layers remain pre-allocated via `toxin_layers` and `_toxin_layers_write`, but they are no
longer propagated by an environmental diffusion helper. The signaling phase rebuilds them locally
each tick from currently active emitters.

## Diffusion Model

The environment defines a precomputed Gaussian kernel through `DIFFUSION_KERNEL`, built by
`_make_gaussian_kernel()`.

### Current signal diffusion procedure

`diffuse_signals()` currently performs, for each signal layer:

1. compute the mean wind vector,
2. convolve the layer with `DIFFUSION_KERNEL` using `scipy.signal.convolve2d`,
3. advect by integer cell shifts using `np.roll`,
4. zero values below `SIGNAL_EPSILON`,
5. write into the signal write buffer,
6. swap read and write buffers.

### Toxin locality procedure

Toxin layers do not use Gaussian diffusion.

Instead, signaling clears toxin layers at the start of the phase and rewrites only the cells of
currently active toxin-emitting plants. This keeps toxins local to plant tissue and avoids airborne
Gaussian spread.

## Subnormal Float Mitigation

After convolution and wind shifting, signal diffusion zeroes out values below `SIGNAL_EPSILON`.

This is not cosmetic cleanup. It is a performance invariant motivated by the cost of processing
subnormal floating-point tails. In PHIDS, sparsity preservation is part of the computational model.

## Wind Semantics

The environment currently supports two wind update modes:

- `set_uniform_wind(vx, vy)` for full-field updates,
- `update_wind_at(x, y, vx, vy)` for cell-local mutation.

The live REST interface primarily exercises the uniform update pathway.

## Plant-Energy API

The current plant-energy helper methods are:

- `set_plant_energy(x, y, species_id, value)`
- `clear_plant_energy(x, y, species_id)`
- `rebuild_energy_layer()`

A notable invariant is that `set_plant_energy()` clamps values to `>= 0.0` before storing them in
write buffers.

## Serialization Role

`GridEnvironment.to_dict()` converts the current environment layers into list-backed structures
suitable for msgpack serialization and WebSocket transport.

This makes `GridEnvironment` the backbone of the replay and streaming snapshot formats.

## Read/Write Boundary in Practice

The current engine does not implement a universally duplicated whole-world state. Instead, it uses
**field-level double-buffering** for the environment combined with deterministic phase ordering.

This is the most precise description of the present runtime model:

- buffered environmental layers,
- ordered ECS mutation passes,
- synchronization at phase boundaries through rebuild/swap operations.

## Evidence from Tests

The current test suite verifies key environmental properties.

### Diffusion thresholding

`tests/test_biotope_diffusion.py` verifies that tiny signal concentrations are truncated to zero
after diffusion.

### Buffer-swap and invariants

`tests/test_schemas_and_invariants.py` verifies that:

- invalid grid dimensions raise errors,
- plant-energy writes become visible only after `rebuild_energy_layer()`,
- clearing plant energy is reflected after a rebuild,
- negative energy writes are clamped to zero.

## Methodological Limits of the Current Biotope

The current environment model should be described precisely:

- wind advection is represented by integer rolls of the convolved field,
- diffusion is layer-based rather than particle-based,
- toxins are rebuilt locally by signaling rather than passed through diffusion,
- double-buffering is strongest at the field level rather than as a full read/write universe clone.

These are important characteristics of the current scientific and computational model.

## Verified Current-State Evidence

- `src/phids/engine/core/biotope.py`
- `src/phids/engine/loop.py`
- `tests/test_biotope_diffusion.py`
- `tests/test_schemas_and_invariants.py`

## Where to Read Next

- For entity locality and cell occupancy: [`ecs-and-spatial-hash.md`](ecs-and-spatial-hash.md)
- For the global guidance surface written into the environment: [`flow-field.md`](flow-field.md)
- For system-level context: [`index.md`](index.md)
