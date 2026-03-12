# Flow Field

The PHIDS flow field is the engine’s global guidance surface for swarm navigation. Instead of
computing individual pathfinding solutions for each swarm, PHIDS computes one scalar field per tick
and lets movement logic read from that shared field.

This chapter documents the current implementation in `src/phids/engine/core/flow_field.py` and its
use within the simulation loop.

## Architectural Role

The flow field is one of PHIDS’s clearest methodological commitments.

Rather than running per-agent BFS or other individualized search procedures, the engine constructs a
single grid-aligned scalar surface that encodes:

- attraction from plant energy,
- repulsion from toxin concentration,
- immediate neighborhood propagation.

Swarm movement then reduces to selecting the best neighboring cell according to that field.

## Runtime Position

In `SimulationLoop.step()`, flow-field generation is the first ecological phase of the tick:

- `compute_flow_field(self.env.plant_energy_layer, self.env.toxin_layers, ...)`

This means all subsequent movement behavior reads the field generated from the pre-interaction,
current read-visible environment state.

## Current Computational Structure

The flow-field module currently exposes:

- `_compute_flow_field_impl(...)` — shared pure-Python implementation,
- `_compute_flow_field` — Numba-compiled alias of that implementation,
- `compute_flow_field(...)` — public wrapper that sums toxin layers and delegates to the compiled
  kernel,
- `apply_camouflage(...)` — in-place attenuation helper for plant camouflage.

This structure has two important consequences:

1. the runtime hot path remains Numba-compiled,
2. the underlying kernel logic remains directly testable and coverable.

## Current Mathematical Procedure

The current kernel follows a simple two-stage procedure.

### 1. Base gradient construction

For each cell `(x, y)`, the kernel computes:

- `gradient[x, y] = plant_energy[x, y] - toxin_sum[x, y]`

This establishes the local scalar value before propagation.

### 2. One-pass neighborhood propagation

The kernel then performs a single propagation pass in which each cell:

- contributes its own value to the same cell,
- contributes `value * 0.5` to each 4-connected neighbor.

The current decay constant is therefore:

- `decay = 0.5`

The result is a BFS-like local spreading effect, but implemented as a deterministic single-pass
array procedure rather than an explicit queue-driven traversal.

## Interpretation

The current flow field should be interpreted as a local guidance heuristic rather than as a full
potential-field solver over many iterations.

It encodes:

- strong attraction at plant-energy sources,
- negative contributions at toxin sources,
- immediate one-hop influence from neighboring cells.

This is sufficient for the current interaction system, which only compares the current cell with its
4-connected neighbors.

## Toxin Handling

The public `compute_flow_field()` wrapper first aggregates all toxin layers via:

- `toxin_layers.sum(axis=0)`

This means the current flow field does not distinguish toxin layers during navigation; it consumes a
single summed repulsion surface.

## Camouflage Integration

After the global flow field has been computed, `SimulationLoop.step()` traverses live plants and
calls `apply_camouflage()` for plants with camouflage enabled.

This means camouflage is currently modeled as a post-processing attenuation of the flow field at the
plant’s cell, not as a modification of plant energy itself.

## Consumer in the Interaction System

`run_interaction()` uses the flow field through `_choose_neighbour_by_flow_probability(...)`, which
deterministically compares the current cell with its 4-connected neighbors and chooses:

- the maximum field value for normal pursuit,
- the minimum field value when inverted behavior is requested.

This completes the architectural story:

- one field is written globally,
- many swarms read it locally,
- no individualized path planner is needed.

## Performance Significance

The flow field is one of the most benchmark-sensitive components in PHIDS because:

- it is computed every tick,
- it has global influence over swarm behavior,
- it is a natural hotspot for large grids.

For that reason, the kernel is Numba-compiled and covered by dedicated benchmark tests.

## Evidence from Tests

The current flow-field tests verify several important behaviors.

### Zero-input no-op

A zero field produces a zero result.

### Degenerate dimensions

Tests cover single-row and single-column cases, ensuring the branch logic for grid edges is not only
correct on square interiors.

### Plant attraction and toxin repulsion

The tests verify that positive plant energy and negative toxin contribution combine correctly.

### Multi-layer toxin summation

The wrapper behavior is explicitly tested so that toxin-layer aggregation remains part of the public
contract.

### Linearity / superposition

The kernel is tested for additive behavior across multiple source fields.

### Camouflage attenuation

Tests confirm that camouflage scales a single flow-field cell in place and supports both full and
zero attenuation.

### Benchmark expectation

`tests/test_flow_field_benchmark.py` verifies that the flow-field generation path remains a
benchmark-tracked hotspot.

## Methodological Limits of the Current Flow Field

The current implementation should be described precisely rather than idealized.

- it is a single-pass propagation model, not a multi-iteration equilibrium field,
- it uses 4-connectivity rather than diagonal influence,
- it collapses all toxin layers into one summed repulsion surface,
- it relies on local comparison in the interaction phase rather than long-horizon route planning.

These are not defects in documentation; they are the present mathematical design of PHIDS.

## Verified Current-State Evidence

- `src/phids/engine/core/flow_field.py`
- `src/phids/engine/loop.py`
- `src/phids/engine/systems/interaction.py`
- `tests/test_flow_field.py`
- `tests/test_flow_field_benchmark.py`

## Where to Read Next

- For the environmental layers that supply plant energy and toxins: [`biotope-and-double-buffering.md`](biotope-and-double-buffering.md)
- For the discrete movement consumers of the field: [`ecs-and-spatial-hash.md`](ecs-and-spatial-hash.md)
- For the engine-wide execution order: [`index.md`](index.md)
