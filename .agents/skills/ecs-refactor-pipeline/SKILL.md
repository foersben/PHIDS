---
name: ecs-refactor-pipeline
type: Agent Skill
title: ECS Code-Smell Refactoring Pipeline
status: stable
stale_after: "2027-06-01T00:00:00Z"
version: 1.0
description: Autonomous, performance-safe workflow for eliminating code smells from PHIDS cold-path control-plane modules while respecting DOD/JIT hot-path immutability constraints.
tags: [workflow, refactor, ecs, code-smell, performance-gate, cold-path]
generated: {by: process:agent-os-refactor, at: "2026-10-30T00:00:00Z"}
verified: {by: process:agent-os-refactor, at: "2026-10-30T00:00:00Z"}
globs:
- src/phids/api/**/*.py
- src/phids/telemetry/**/*.py
- src/phids/engine/batch/**/*.py
- src/phids/engine/core/herbivore_params.py
- src/phids/engine/systems/interaction/feeding.py
- src/phids/engine/systems/signaling/lifecycle.py
- tests/**/*.py
---

# ECS Code-Smell Refactoring Pipeline

## Trigger & Purpose

Run `/ecs-refactor-pipeline` when iterating on PHIDS cold-path code quality without regressing
simulation correctness or hot-path throughput. This workflow applies a zero-regression loop
enforcing equivalence checks, deterministic state replay parity, and a hard benchmark rollback
gate at every step.

**Read `.agents/rules/06-clean-code-and-antipatterns.md` before executing any step.**

---

## Pre-Conditions

Before starting any iteration:

1. Confirm the working tree is clean: `git status` must report no uncommitted changes.
2. Record the current HEAD: `git rev-parse HEAD`.
3. The pre-commit hook must pass: `just check`.

---

## Step 1 - Target Selection

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
(leaf modules first). Never select a hot-path module (see `.agents/rules/06-clean-code-and-antipatterns.md`
Hot-Path Protected List).

Output: Document the chosen module, function, and specific smell being eliminated.

---

## Step 2 - Baseline Capture

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

## Step 3 - Surgical Refactor

Apply the targeted refactoring adhering to the three golden rules:

1. **Smell A Fix:** Replace `tuple[float, int, bool]` returns with a typed `NamedTuple` or `@dataclass(slots=True, frozen=True)`.
2. **Smell B Fix:** Replace `getattr(obj, "field", default)` with direct attribute access `obj.field` if statically typed, or explicit dictionary lookup if dynamically keyed.
3. **Smell C Fix:** Remove redundant scalar casts if the underlying type is already guaranteed by Pydantic schemas or NumPy array dtypes.

---

## Step 4 - Verification Gates

Run full verification suite:

```bash
# 1. Type and lint checks
uv run ruff check --fix src/
uv run mypy src/phids/

# 2. Correctness and invariants
just test-parity
just test-replay
just test-matrix

# 3. Full test suite
just test
```

If any test fails, revert changes via `git checkout -- <file>` and document root cause in findings.

---

## Step 5 - Benchmark & Allocation Regression Gate

Confirm performance invariance:

```bash
just benchmark 2>&1 | tee /tmp/bench_after.txt
uv run pytest --no-cov -m heap_allocation -v 2>&1 | tee /tmp/heap_after.txt
```

Compare `bench_before.txt` vs `bench_after.txt`. If mean latency increases > 1% on any benchmark, rollback immediately.
