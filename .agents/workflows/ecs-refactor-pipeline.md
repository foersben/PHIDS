---
type: Agent Workflow
title: ECS Code-Smell Refactoring Pipeline
status: stable
stale_after: "2027-06-01T00:00:00Z"
version: 1.0
description: Autonomous, performance-safe workflow for eliminating code smells from
  the PHIDS cold-path control-plane modules while respecting DOD/JIT hot-path
  immutability constraints.
tags: [workflow, refactor, ecs, code-smell, performance-gate, cold-path]
generated: {by: process:ecs-refactor, at: "2026-09-15T01:34:00Z"}
verified: {by: process:ecs-refactor, at: "2026-09-15T01:34:00Z"}
globs:
- src/phids/api/**/*.py
- src/phids/telemetry/**/*.py
- src/phids/engine/batch/**/*.py
- src/phids/engine/core/herbivore_params.py
- src/phids/engine/systems/interaction/feeding.py
- src/phids/engine/systems/signaling/lifecycle.py
- tests/**/*.py
---

# Trigger & Purpose

Run `/ecs-refactor-pipeline` when iterating on PHIDS cold-path code quality without regressing
simulation correctness or hot-path throughput. This workflow applies a zero-regression loop
enforcing equivalence checks, deterministic state replay parity, and a hard benchmark rollback
gate at every step.

**Read `.agents/rules/ecs-clean-code.md` before executing any step.**

---

# Pre-Conditions

Before starting any iteration:

1. Confirm the working tree is clean: `git status` must report no uncommitted changes.
2. Record the current HEAD: `git rev-parse HEAD`.
3. The pre-commit hook must pass: `just check`.

---

# Step 1 - Target Selection

Select the next refactor target using the following priority order:

1. **Smell A (High Priority)** - Positional `tuple[...]` returns in cold-path leaf modules.
   Priority queue:
   * `src/phids/api/presenters/dashboard/payloads.py` - `_compute_plant_metrics`
   * `src/phids/telemetry/conditions.py` - `_gather_flora_metrics`, `_gather_herbivore_metrics`
   * `src/phids/engine/batch/aggregation.py` - `_extract_species_ids`
   * `src/phids/api/routers/batch.py` - `_export_csv`, `_export_tex_table`
   * `src/phids/api/routers/config/flora.py` - `_find_flora_species`
   * `src/phids/api/routers/telemetry/exports.py` - `_build_csv_payload`, `_build_json_payload`
   * `src/phids/api/routers/config/placements.py` - `_extract_autoassign_weights`
   * `src/phids/analytics/dse_optimizer.py` - `evaluate_candidate`

2. **Smell B (High Priority)** - `getattr()` on schema/dataclass fields with known names.
   Priority queue:
   * `src/phids/engine/core/herbivore_params.py` - `get_herbivore_evasion_duration`, `get_herbivore_softmax_temperature`
   * `src/phids/engine/systems/interaction/movement/core.py` - `getattr(swarm, "aversion_memory")`
   * `src/phids/engine/systems/interaction/movement/anchoring.py` - `getattr(swarm, "last_caloric_intake")`, `"metabolism_upkeep"`
   * `src/phids/engine/systems/interaction/feeding.py` - `getattr(p, "handling_time")` x2
   * `src/phids/engine/systems/signaling/lifecycle.py` - `getattr(plant, "target_nutrition_factor")`

3. **Smell C (Medium Priority)** - Redundant `float()` / `int()` / `bool()` casts on already-typed fields.

**Selection Rule**: Always pick the highest-priority smell in the module with fewest dependencies
(leaf modules first). Never select a hot-path module (see `.agents/rules/ecs-clean-code.md`
Hot-Path Protected List).

Output: Document the chosen module, function, and specific smell being eliminated.

---

# Step 2 - Baseline Capture

Before touching any code:

```bash
# 1. Record the current benchmark baselines
just benchmark 2>&1 | tee /tmp/bench_before.txt

# 2. Run the heap allocation invariant
uv run pytest --no-cov -m heap_allocation -v 2>&1 | tee /tmp/heap_before.txt

# 3. Record baseline test count and coverage
just test 2>&1 | tail -20 | tee /tmp/test_before.txt
```

Parse and store:
* Mean latency (ns) for each benchmark test from `bench_before.txt`.
* `total_new_bytes` from `heap_before.txt`.
* Test pass count from `test_before.txt`.

The 1% latency rollback thresholds are defined in `.agents/memory/ecs-refactor-findings.md`.

---

# Step 3 - Scoped Refactor

Apply exactly **one smell elimination per iteration**. The scope must be a single function or
a cohesive group of 2-3 functions in the same module implementing the same pattern.

## Smell A: Converting Positional Tuple Returns to `@dataclass(slots=True, frozen=True)`

1. Define a new `@dataclass(slots=True, frozen=True)` return type in the **same file** (or in
   a local `_types.py` if the module already imports from a shared types module).
2. Name the dataclass after the function's conceptual return (e.g., `PlantMetrics`,
   `FloraMetrics`, `ExportResult`).
3. Update the function signature return annotation.
4. Update all call sites within the same module and across the codebase.
5. Run `just lint` to fix any import ordering issues.

**Constraint**: Do not introduce shared mutable state. All new dataclasses must be `frozen=True`
to prevent accidental mutation at call sites.

## Smell B: Replacing `getattr()` with Direct Attribute Access

1. Check the component or schema definition to confirm the field exists.
   * For `SwarmComponent`: inspect `src/phids/engine/components/swarm.py`.
   * For `HerbivoreSpeciesParams`: inspect `src/phids/api/schemas/species.py`.
2. If the field is missing from the dataclass/schema, **add it with the same default** before
   proceeding. Do not change defaults.
3. Replace `getattr(obj, "field_name", default)` with `obj.field_name`.
4. Remove the `# TODO: Performance` comment if present.

**Constraint**: When the `getattr` is in a JIT-decorated function (`@njit`), the field must be
on the component ECS dataclass (`@dataclass(slots=True)`). Do not introduce `getattr` into any
`@njit` body. Verify with `just test-parity` after.

## Smell C: Removing Redundant Casts

1. Replace `float(x)` where `x: float`, `int(y)` where `y: int`, `bool(z)` where `z: bool`
   with bare `x`, `y`, `z`.
2. Run `just lint` (mypy strict will confirm type correctness).

---

# Step 4 - Equivalence Check

```bash
just test         # Full test suite - must pass at same count or higher
just test-parity  # JIT vs pure-Python numerical parity
just test-replay  # Zarr bit-exact replay
just test-scientific  # Scientific invariants
just test-matrix  # Data-Flow Matrix parity
```

**On any failure**:
```bash
git checkout <modified_files>
```

Report the failure and reason. Do NOT proceed to Step 5. Return to Step 1 with the same target
and a corrected approach, or skip to the next target if the smell is in a hot-path module that
was misclassified.

---

# Step 5 - Performance Gate

```bash
just benchmark 2>&1 | tee /tmp/bench_after.txt
uv run pytest --no-cov -m heap_allocation -v 2>&1 | tee /tmp/heap_after.txt
```

Compare each benchmark mean against the Step 2 baseline.

**Hard Rollback Condition**:
* Any benchmark mean increased by > 1% relative to baseline, OR
* `total_new_bytes` from heap invariant exceeds 2048 bytes.

```bash
git checkout <modified_files>
echo "ROLLBACK: Performance regression detected. Reverted."
```

---

# Step 6 - Commit

```bash
just lint
just check

git add <modified_files>
git commit -m "refactor(<module>): <smell_type> - <one_line_description>

- Smell: <Smell A|B|C> - <description>
- Function(s): <fn1>, <fn2>
- Change: <what was changed>
- Benchmark delta: <+/-X ns or 'no regression'>
- Tests: 1250 passed / heap: <N bytes>
"
git push
```

---

# Iteration Loop

After a successful commit, return to Step 1 and select the next target. Stop when:
* All Smell A and B items in the priority queue are resolved.
* `just lint` reports zero issues.
* `just test` passes with coverage >= 82%.
* `just benchmark` shows no regressions vs. `ecs-refactor-findings.md` baselines.
