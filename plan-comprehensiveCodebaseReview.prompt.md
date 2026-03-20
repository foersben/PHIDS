## Comprehensive Codebase Review Plan (Status-Tracked)

Status legend:
- `REALIZED`: implemented and covered by focused tests.
- `IN PROGRESS`: implemented partially, breadth/depth still expanding.
- `OPEN`: not yet addressed in this review cycle.

## Phase Status

1. `REALIZED` - High-risk correctness/performance pass (engine loop, telemetry, websocket payload path)
2. `REALIZED` - Contract/API hardening for `/ws/ui/stream` columnar schema
3. `REALIZED` - Testing quality uplift (property + mutation pilots + benchmark budgets)
4. `IN PROGRESS` - Maintainability pass (debt/shims/typing sweep)
5. `OPEN` - Docs/DevEx pass (drift alignment and onboarding accuracy)

## Realized Work (Evidence-Backed)

### A) Engine + telemetry aggregation and duplicate-scan removal
- Shared per-tick ECS aggregation via `TickMetrics` is integrated across loop, telemetry, and termination checks.
- `SimulationLoop` debug summary now consumes telemetry row values / shared metrics instead of re-scanning ECS.
- Evidence:
  - `src/phids/engine/loop.py`
  - `src/phids/telemetry/tick_metrics.py`
  - `src/phids/telemetry/analytics.py`
  - `src/phids/telemetry/conditions.py`

### B) UI websocket hot-path optimizations
- Compact JSON serialization is enforced for UI streaming (`separators=(",", ":")`).
- Payload cache signatures prevent repeated encoding for unchanged `(loop identity, tick/state signature)`.
- Evidence:
  - `src/phids/api/websockets/manager.py`
  - `tests/integration/api/test_websocket_manager.py`

### C) Columnar dashboard payload contract hardening
- Live dashboard payload is locked to strict columnar `plants`/`swarms` tables.
- Contract snapshot and structural tests guard against schema regressions.
- Evidence:
  - `src/phids/api/presenters/dashboard.py`
  - `tests/unit/api/test_dashboard_presenter.py`
  - `tests/unit/api/fixtures/ui_stream_contract_v1.json`

### D) Phase 3 pilot tests landed for arithmetic-critical logic
- Interaction invariants now cover isolated attrition, reproduction, and mitosis sub-phases.
- Mutation pilots exist for termination logic, interaction arithmetic, and flow-field behavior.
- Mutation pilot breadth now includes signaling trigger-condition branches and dashboard columnar union branches.
- Bounded signaling condition-tree truth-table invariants now run under the Hypothesis pilot lane.
- Marker-based pilot lane selection is now wired for deterministic local/CI execution (`mutation_pilot`, `hypothesis_pilot`).
- Dashboard payload benchmark now emits warning/fail budget checks for mean and p95 latency with environment overrides.
- Evidence:
  - `tests/integration/systems/test_interaction_property_invariants.py`
  - `tests/integration/systems/test_interaction_hypothesis_pilot.py`
  - `tests/integration/systems/test_interaction_mutation_pilot.py`
  - `tests/integration/systems/test_signaling_hypothesis_pilot.py`
  - `tests/integration/systems/test_signaling_mutation_pilot.py`
  - `tests/unit/api/test_dashboard_mutation_pilot.py`
  - `tests/benchmarks/test_dashboard_payload_benchmark.py`
  - `tests/unit/telemetry/test_termination_mutation_pilot.py`
  - `tests/unit/engine/core/test_flow_field_mutation_pilot.py`
  - `pyproject.toml`
  - `.github/workflows/ci.yml`

### E) Phase 4 maintainability kick-off (typing/debt)
- `SimulationLoop` replay backend dispatch now uses an explicit typed contract instead of dynamic `Any`/`hasattr` branching.
- Optional Zarr import typing now uses explicit cross-branch symbol declaration to eliminate static-analysis ambiguity.
- Replay append branching is now isolated in a dedicated helper (`_append_replay_frame`) to reduce phase-loop complexity and centralize backend-specific behavior.
- Signaling trigger pipelines now use explicit `TriggerConditionSchema` typing from loop cache to signaling execution, removing redundant runtime trigger type guards.
- UI HTML router handlers now return concrete `Response` annotations instead of `Any`, improving endpoint typing consistency.
- Batch HTML fragment handlers now return concrete `Response` annotations instead of `Any`, improving endpoint typing consistency across router surfaces.
- Simulation control handlers now return explicit `Response` objects for mixed HTMX/JSON branches, avoiding broad `Any` unions in route annotations.
- Telemetry fragment handlers now return concrete `Response` annotations instead of `Any`, and telemetry numeric coercion uses typed `object` input guards.
- Config draft-mutation handlers now return concrete `Response` annotations instead of `Any`, improving typing consistency across the largest HTMX router partition.
- Batch aggregate view/export handlers now use typed JSON aggregate normalization helpers to reduce `Any` hotspots while preserving CSV/TeX/TikZ behavior.
- Replay raw-array ingestion now uses explicit structural environment contracts in both msgpack and Zarr replay backends, reducing `Any` in hot replay paths.
- Msgpack replay payload serialization/deserialization now uses explicit `ReplayState`/`ReplayValue` aliases with decode-shape guards, tightening type safety at the replay I/O boundary.
- Zarr replay metadata and frame reconstruction now use typed metadata entries plus `ReplayState`/`ReplayValue` aliases, reducing dynamic type escape hatches in the storage backend.
- Legacy `.bin` migration in the Zarr backend now reuses typed msgpack deserialization (`deserialise_state`) and validates non-mapping payloads via focused replay tests.
- Scenario I/O helpers now use explicit typed JSON mapping aliases with root-object validation to reduce `Any` at the configuration ingest boundary.
- Batch engine aggregation/sanitization paths now use explicit telemetry/JSON aliases and numeric coercion helpers, reducing `Any` in batch summary generation.
- Telemetry recorder row buffering and dataframe flattening now use explicit telemetry row/species-map aliases, reducing `Any` in the analytics accumulation path.
- Signaling activation-condition evaluation and active-toxin property merging now use explicit typed node/property contracts, removing remaining `Any` hotspots in this system.
- API composition helper contracts in `api.main` now use object-based mapping/list annotations for condition parsing, trigger-context construction, and live diagnostics helpers.
- Config router flora/herbivore patch payloads and trigger-condition node traversal now use object-typed maps, removing remaining router-level `Any` hotspots.
- Simulation loop species lookup caches and debug-summary metric extraction now use schema/telemetry-specific typing with deterministic scalar coercion helpers.
- Integration coverage now asserts both Zarr raw-array append and msgpack snapshot fallback replay paths.
- Evidence:
  - `src/phids/engine/loop.py`
  - `src/phids/engine/systems/signaling.py`
  - `src/phids/api/routers/ui.py`
  - `src/phids/api/routers/batch.py`
  - `src/phids/api/routers/simulation.py`
  - `src/phids/api/routers/telemetry.py`
  - `src/phids/api/routers/config.py`
  - `src/phids/api/main.py`
  - `src/phids/io/replay.py`
  - `src/phids/io/zarr_replay.py`
  - `src/phids/io/scenario.py`
  - `src/phids/engine/batch.py`
  - `src/phids/telemetry/analytics.py`
  - `tests/integration/systems/test_termination_and_loop.py`
  - `tests/integration/api/test_api_simulation_and_scenario_routes.py`
  - `tests/integration/api/test_ui_routes.py`

## Open Work by Review Area

### 1) Architecture & Boundaries (`OPEN`)
- Re-run a full boundary audit (`api -> services/presenters -> engine -> telemetry/io`) after recent optimizations.
- Reconfirm draft-vs-live separation invariants under complex UI edit/load flows.

### 2) Correctness & Determinism (`IN PROGRESS`)
- Expand determinism coverage to replay/serialization round-trip and seeded reproducibility across longer runs.
- Extend floating-point edge-case assertions around `SIGNAL_EPSILON` in broader integration scenarios.

### 3) Performance & Memory (`IN PROGRESS`)
- Dashboard, websocket encode, diffusion hotspot, and replay/export serialization benchmark budget assertions are in place (warning/fail thresholds + p95 telemetry).
- Review residual allocation churn in hot loops beyond already-optimized websocket/aggregation paths.

### 4) API/UI Contracts (`IN PROGRESS`)
- Broaden contract checks from payload shape to route-level diagnostics/error semantics.
- Formalize backward-compatibility policy for UI stream `contract_version` evolution.

### 5) Code Quality & Maintainability (`OPEN`)
- Sweep for stale shims/comments and dead paths introduced by earlier refactors.
- Run a focused typing-hole pass (`Any` hotspots, mypy strictness opportunities).

### 6) Testing Strategy (`IN PROGRESS`)
- Property testing: pilots now include interaction arithmetic, signaling condition-tree semantics, termination parity, and replay spill/load plus truncation and header-corruption invariants.
- Mutation testing: pilots now include termination, interaction, signaling, dashboard, and flow-field branch sentinels; monitor runtime budget.
- Flakiness: add deterministic stress matrix for order/race-sensitive surfaces.

### 7) Security & Operational Hardening (`OPEN`)
- Verify websocket lifecycle/resource cleanup under reconnect storms and failure injection.
- Audit file I/O safety paths for replay/export and path-handling constraints.

### 8) Docs & Developer UX (`OPEN`)
- Reconcile docs with latest contract/performance changes (engine + websocket + telemetry sections).
- Validate runbooks and contributor guidance against current test commands and architecture reality.

## Next Steps (Execution Order)

1. Finish Phase 3 hardening:
   - Phase 3 pilot breadth and benchmark budget targets are now realized.
2. Execute Phase 4 maintainability sweep:
   - Remove stale shims/comments and resolve top typing holes.
3. Execute Phase 5 docs/DevEx alignment:
   - Update architecture/performance docs and runbook snippets.
4. Produce final ranked findings and follow-on roadmap.

## Deliverables Status

- Ranked findings list: `IN PROGRESS`
- Quick-wins patch set: `REALIZED` (multiple landed items in Phase 1-3)
- Structural improvements roadmap: `OPEN`
- Testing uplift plan: `REALIZED` (pilot lanes and benchmark budgets integrated)
- AGENTS/docs update proposals: `OPEN` (evaluate at end of maintainability + docs pass)
