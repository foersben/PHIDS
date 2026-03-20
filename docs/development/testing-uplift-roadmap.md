# Testing Uplift Roadmap

This roadmap defines the next incremental testing upgrades for PHIDS after the Phase 1 high-risk review pass. The objective is to improve mutation resistance, bounded invariant coverage, and performance regression detection without destabilizing CI runtime or violating deterministic test constraints.

## Current State

PHIDS already includes targeted mutation and property pilots, branch-focused integration coverage, and benchmark guards for core hot paths. Recent upgrades include:

- termination mutation pilot coverage in `tests/unit/telemetry/test_termination_mutation_pilot.py`,
- interaction mutation pilot coverage in `tests/integration/systems/test_interaction_mutation_pilot.py`,
- flow-field mutation pilot coverage in `tests/unit/engine/core/test_flow_field_mutation_pilot.py`,
- bounded Hypothesis interaction pilot coverage in `tests/integration/systems/test_interaction_hypothesis_pilot.py`,
- signaling mutation/property pilot coverage in `tests/integration/systems/test_signaling_mutation_pilot.py` and `tests/integration/systems/test_signaling_hypothesis_pilot.py`,
- dashboard mutation pilot coverage in `tests/unit/api/test_dashboard_mutation_pilot.py`,
- bounded Hypothesis termination parity coverage in `tests/unit/telemetry/test_termination_hypothesis_pilot.py`,
- bounded Hypothesis replay round-trip coverage in `tests/unit/io/test_replay_hypothesis_pilot.py`,
- explicit warning/fail budget checks and p95 warning telemetry in `tests/benchmarks/test_dashboard_payload_benchmark.py`,
- websocket encode-path budget checks in `tests/benchmarks/test_websocket_encode_benchmark.py`,
- diffusion hotspot benchmark coverage in `tests/benchmarks/test_diffusion_hotspot_benchmark.py`,
- replay/export serialization benchmark budget checks in `tests/benchmarks/test_replay_export_serialization_benchmark.py`.

These controls reduce immediate risk, but broader consistency is still pending across additional subsystems and statistical gate depth.

## Target State

The target state is a three-lane testing strategy with explicit entry commands and bounded runtime behavior:

1. mutation pilots for mutation-prone branch semantics,
2. bounded property-based pilots for arithmetic and monotonicity invariants,
3. benchmark budget gates for performance-critical runtime surfaces.

Each lane must remain deterministic, focused, and discoverable in development documentation.

## Lane 1: Mutation Uplift

Mutation pilots should expand from existing telemetry/interaction/flow-field pilots to additional high-value branch surfaces where operator mistakes are common (threshold polarity, precedence ordering, and fail-open logic).

### Near-Term Expansion Targets

- `src/phids/io/replay.py` and `src/phids/io/zarr_replay.py` branch-critical replay paths
- `src/phids/telemetry/conditions.py` edge-case termination parity surfaces

### Guardrails

- Keep pilot tests narrowly scoped and branch-targeted.
- Prefer deterministic fixtures and explicit expected outcomes.
- Avoid introducing heavy randomized loops in mutation pilots.
- Keep marker selection explicit (`mutation_pilot`) for CI-friendly lane execution.

## Lane 2: Property-Based Uplift

Bounded Hypothesis pilots should remain in optional lanes and focus on invariants that are hard to cover with static parameter grids alone.

### Near-Term Expansion Targets

- replay spill/load invariants for bounded frame windows.

### Guardrails

- Keep sampled cardinalities Rule-of-16 aligned.
- Use finite sampled float sets where possible.
- Keep marker selection explicit (`hypothesis_pilot`) and deterministic.

## Lane 3: Performance Gates Uplift

Current benchmarks cover flow-field computation, spatial hash access, and dashboard payload assembly, including warning telemetry for mean and p95 latency. The next uplift step is extending benchmark surface area while keeping CI variance manageable.

### Near-Term Expansion Targets

- benchmark trigger-policy reinforcement for long-horizon Zarr replay paths.

### Guardrails

- Keep fail thresholds configurable via environment variables.
- Use warning thresholds before introducing stricter fail criteria.
- Preserve existing focused benchmark selection behavior (`-m 'not benchmark'`).

## Execution Order

1. Expand mutation pilots for signaling and dashboard contract branches.
2. Add one bounded Hypothesis pilot for signaling condition-tree behavior.
3. Promote stable warning thresholds to fail gates after observed baseline convergence.
4. Extend benchmark guards to long-horizon Zarr replay paths.

## Verification Commands

Use the following minimal command set when iterating on this roadmap:

```bash
uv run pytest -o addopts='' -m mutation_pilot -q
uv run pytest -o addopts='' -m hypothesis_pilot -q
uv run pytest -o addopts='' -m "mutation_pilot or hypothesis_pilot" -q
uv run pytest -o addopts='' tests/benchmarks/test_flow_field_benchmark.py tests/benchmarks/test_spatial_hash_benchmark.py tests/benchmarks/test_dashboard_payload_benchmark.py tests/benchmarks/test_websocket_encode_benchmark.py tests/benchmarks/test_diffusion_hotspot_benchmark.py tests/benchmarks/test_replay_export_serialization_benchmark.py -q
uv run mkdocs build --strict
```

## Ownership and Update Policy

This roadmap should be updated when one of the following occurs:

- a new pilot lane is added,
- benchmark budget policy changes,
- CI selection policy for mutation/property/benchmark lanes changes.

Routine endpoint or schema edits should not modify this roadmap unless they alter lane structure or test-selection policy.
