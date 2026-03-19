## Review Overview (What To Check)

### 1) Architecture & Boundaries
- Layer integrity: `api -> services/presenters -> engine -> telemetry/io`.
- Draft-vs-live state separation (`DraftState` vs `SimulationLoop`) correctness.
- ECS/data-oriented constraints upheld (no object-graph drift).
- Double-buffering discipline in environment updates.
- Hot-path ownership respected (e.g., flow-field/interaction/signaling boundaries).

### 2) Correctness & Determinism
- Tick-order invariants and phase semantics.
- Termination correctness (`Z1..Z7`) and shared aggregation consistency.
- Replay/serialization round-trip and schema stability.
- Floating-point threshold invariants (`SIGNAL_EPSILON`) and edge behavior.
- Randomness handling and reproducibility in tests.

### 3) Performance & Memory
- UI stream payload build/serialize hotspots (`/ws/ui/stream`).
- ECS query multiplicity and duplicate scans per tick.
- Allocations in hot loops (Python object churn, per-tick dict/list creation).
- Spatial hash usage vs accidental O(N^2) fallbacks.
- Benchmark coverage gaps (currently likely under-covered outside core hotspots).

### 4) API/UI Contracts
- Contract stability for websocket payloads and route schemas.
- Frontend assumptions vs backend payload evolution.
- Backward compatibility policy (what must remain stable vs can be tightened).
- Error handling + diagnostics quality for operators.

### 5) Code Quality & Maintainability
- Boilerplate / stale comments / `FIX`/`TODO` residue.
- Dead code and compatibility shims no longer needed.
- Naming clarity and consistency of domain terms.
- Type safety (mypy strictness, typing holes, `Any` spread).
- Reusable patterns vs copy/paste variants.

### 6) Testing Strategy (Advanced)
- Unit/integration/e2e/benchmark test balance and overlap.
- Flakiness detection (order-dependent tests, random monkeypatch sensitivity).
- Property-based testing opportunities (Hypothesis) for invariants.
- Mutation testing adoption plan (targeted first, then broader).
- Performance regression gates with explicit budgets.

### 7) Security & Operational Hardening
- Input validation boundaries (Pydantic ingress completeness).
- Websocket lifecycle and resource handling.
- File IO safety for replay/export paths.
- CI quality gate sufficiency and branch-trigger policy fit.

### 8) Docs & Developer UX
- Docs-to-code drift (especially architecture/performance docs).
- Runbook accuracy (commands, assumptions, caveats).
- AGENTS/Contributor guidance consistency with actual patterns.

## How To Execute The Review (Phased)
1. High-risk correctness/perf pass (engine loop, systems, telemetry, websocket payload path).
2. Contract & API/UI pass (routes, presenters, templates, client assumptions).
3. Testing quality pass (flake risks, mutation-test pilot, property-based candidates).
4. Maintainability pass (shims, stale comments, dead code, typing holes).
5. Docs/DevEx pass (accuracy and onboarding quality).

## Advanced Testing Upgrades (Recommended)
- Mutation testing pilot on critical logic:
  - `src/phids/telemetry/conditions.py`
  - `src/phids/engine/systems/interaction.py`
  - `src/phids/engine/core/flow_field.py`
- Property-based tests for:
  - conservation/monotonicity invariants
  - bounds/sparsity behavior
  - deterministic state transitions under seeded RNG
- Contract snapshot tests for `/ws/ui/stream` payload schema.
- Benchmark budget assertions (warning/fail thresholds) for key hotspots.

## Deliverables
- Ranked findings list (severity, impact, file/symbol refs, suggested fix).
- Quick-wins patch set (low-risk, high-value).
- Structural improvements roadmap (larger refactors).
- Testing uplift plan (mutation + property + perf gates).
- Optional AGENTS/docs update proposals for durable project guidance.
