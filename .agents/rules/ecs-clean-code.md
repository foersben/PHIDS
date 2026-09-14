---
type: Reference
title: ECS Clean Code Policy
status: stable
stale_after: "2027-06-01T00:00:00Z"
version: 1.0
description: Boundary constraints distinguishing acceptable clean code from
  DOD design necessities in the PHIDS ECS simulation engine. Enforced during
  the /ecs-refactor-pipeline workflow.
generated: {by: process:ecs-refactor, at: "2026-09-15T01:34:00Z"}
verified: {by: process:ecs-refactor, at: "2026-09-15T01:34:00Z"}
---

# ECS Clean Code Policy

This rule file defines the hard boundaries between hot-path DOD immutability constraints and
cold-path clean code targets. All AI agents running `/ecs-refactor-pipeline` MUST load and
adhere to this file before applying any refactoring.

---

## Hot-Path Protected List

The following modules are on the simulation tick critical path. They contain `@njit`-compiled
Numba kernels, double-buffered ECS arrays, or branchless SIMD float masks.

**Zero structural refactors are permitted without first passing `just test-parity`,
`just test-replay`, and the `heap_allocation` pytest marker.**

```
src/phids/engine/core/diffusion.py
src/phids/engine/core/biotope.py
src/phids/engine/core/flow/stencils.py
src/phids/engine/core/flow/boundaries.py
src/phids/engine/core/flow/solvers.py
src/phids/engine/core/ecs.py
src/phids/engine/systems/interaction/movement/choices.py
src/phids/engine/systems/interaction/movement/neighbors.py
src/phids/engine/systems/interaction/movement/capacity.py
src/phids/engine/systems/interaction/movement/anchoring.py
src/phids/engine/systems/interaction/movement/incidental.py
src/phids/engine/systems/interaction/movement/random_walk.py
src/phids/engine/systems/signaling/emission.py
src/phids/engine/systems/signaling/triggers.py
src/phids/engine/systems/signaling/spatial.py
src/phids/engine/systems/lifecycle/growth.py
src/phids/engine/systems/interaction/population.py
```

---

## Hot-Path Exemptions (What Is Allowed by Design)

These patterns look like code smells to a classical linter but are architectural mandates in the
DOD simulation core. Do not flag or change them:

* **Raw integer entity IDs**: Entity IDs are plain `int` scalars. Do NOT wrap them in value
  objects, ID classes, or named types. The spatial hash and ECS query paths depend on raw int
  comparison.

* **In-place buffer mutations (CQS exemptions)**: Functions that mutate `_write` layer NumPy
  arrays in-place (e.g., `env.signal_layers[...]`, `env.toxin_layers[...]`, plant/swarm
  component fields) are deliberate CQS violations for cache locality. Do NOT convert these to
  return new arrays.

* **Contiguous array pre-allocation outside loops**: `np.zeros`, `np.empty` called once before
  a JIT loop and passed as scratch buffers are correct. Do NOT move allocation inside JIT loops.

* **Float masks instead of `if/else`**: State transitions expressed as
  `delta * alive_mask` or `value * float(condition)` instead of conditional branches are
  correct branchless SIMD patterns. Do NOT convert to `if/else` inside `@njit` bodies.

* **`@njit(cache=True)` on all hot kernels**: JIT caching is mandatory. Do NOT remove it.

* **`tuple[int, int]` coordinate pairs inside JIT functions**: Coordinate pairs `(x, y)` in
  JIT scope are acceptable as Numba can unpack these without Python overhead. Do not convert
  to dataclass inside JIT scope.

---

## Cold-Path Targets (What Must Be Fixed)

These patterns are smells in the cold-path control plane (API, presenters, telemetry,
batch orchestration, config parsers):

### Smell A - Primitive Obsession / Positional Tuple Returns

**Rule**: Any function in a cold-path module returning `tuple[T1, T2, ...]` with 2+ elements
where the elements are logically related (not coordinate pairs) MUST be converted to a
`@dataclass(slots=True, frozen=True)` value object.

**Rationale**: Positional unpacking is fragile on reorder. Named fields make call sites
self-documenting and allow mypy to catch mismatched assignments.

**Exemptions**:
* `tuple[int, int]` coordinate pairs in hot-path JIT scope.
* `tuple[bytes, int]` where bytes is a response body and int is its pre-computed length (these
  are acceptable if no better abstraction exists, but prefer `ExportResult`).

### Smell B - `getattr()` on Typed Dataclass / Pydantic Fields

**Rule**: `getattr(obj, "field_name", default)` is prohibited when:
1. `obj` is a `@dataclass(slots=True)` ECS component, AND
2. The field is statically declared on the dataclass.

Replace with direct attribute access `obj.field_name`. If the field does not exist yet,
add it to the dataclass definition with the same default before replacing the `getattr`.

**Exemption**: `getattr` is permitted for truly dynamic attribute access (e.g., plugin
introspection, optional mixin fields), but these cases do not exist in the PHIDS core engine.

### Smell C - Redundant Type Casts

**Rule**: `float(x)` where `x: float`, `int(y)` where `y: int`, `bool(z)` where `z: bool`
are no-ops that obscure type information and generate Pyrefly warnings. Remove them.

**Exception**: `float(np.float32_value)` is acceptable to ensure Python float (not NumPy scalar)
is serialised into JSON. Check the serialisation context before removing.

### CQS Violations in Cold-Path Orchestration

**Rule**: Command-Query Separation applies to cold-path I/O and orchestration routines.
Functions that both mutate state AND return a result should be split, unless:
* The mutation is a write to an external resource (file, network, database) and the return
  is an acknowledgment (not a derived value from the mutation).

---

## Verification Requirements Per Smell Type

| Smell | Required Checks After Fix |
|-------|--------------------------|
| Smell A (tuple -> dataclass) | `just test` + `just lint` |
| Smell B (`getattr` -> direct) | `just test` + `just test-parity` + `just lint` |
| Smell C (redundant casts) | `just lint` + `just test` |
| Any hot-path touch | `just test` + `just test-parity` + `just test-replay` + `just benchmark` |

---

## Performance Gate Constants

* **Benchmark rollback threshold**: > 1% mean latency regression on any `tests/benchmarks/` test.
* **Heap allocation limit**: `total_new_bytes <= 2048` from `test_flow_field_zero_python_heap_allocation`.
* **Coverage floor**: Total coverage must not drop below 82% after any refactor commit.
* **Complexity ceiling**: No function may exceed cognitive complexity 15 (`uvx complexipy . --failed`).

---

## Commit Convention for Refactor Commits

```
refactor(<module_shortname>): <Smell type> - <one_line_description>
```

Examples:
```
refactor(conditions): Smell A - FloraMetrics/HerbivoreMetrics replace anonymous tuple returns
refactor(herbivore_params): Smell B - direct field access replaces getattr on Pydantic schema
refactor(live): Smell C - remove redundant float/int/bool casts on typed ECS component fields
```
