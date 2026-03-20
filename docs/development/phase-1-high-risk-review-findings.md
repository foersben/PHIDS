# Phase 1 High-Risk Review Findings

This document records the first comprehensive review pass over PHIDS high-risk correctness and performance surfaces. The pass focused on simulation loop phase ordering, signaling/interaction correctness boundaries, telemetry and termination consistency, and `/ws/ui/stream` contract stability.

## Scope and Method

The analysis examined implementation and tests across:

- `src/phids/engine/loop.py`
- `src/phids/engine/systems/{interaction,signaling,lifecycle}.py`
- `src/phids/telemetry/{tick_metrics,conditions,analytics}.py`
- `src/phids/api/presenters/dashboard.py`
- `src/phids/api/websockets/manager.py`
- targeted integration/unit/benchmark tests under `tests/`

The pass used evidence-first validation: each finding was either confirmed by an executable regression test or paired with a deterministic reproducibility argument grounded in current control flow.

## Ranked Findings

### 1) Same-tick stream staleness on non-tick state changes (Fixed)

- **Severity:** High
- **Impact:** UI and simulation websocket subscribers could miss same-tick updates (for example wind changes) because emission/cache signatures keyed only on tick and loop lifecycle booleans.
- **Evidence path:** `SimulationLoop.update_wind` mutates environment state without advancing tick, while stream managers previously emitted only on tick/signature changes.
- **Resolution:** Added `SimulationLoop.state_revision` and included it in stream cache/emission signatures.
- **Patched files:**
  - `src/phids/engine/loop.py`
  - `src/phids/api/websockets/manager.py`
  - `tests/integration/api/test_websocket_manager.py`

### 2) Composite activation conditions could evaluate malformed trees inconsistently (Fixed)

- **Severity:** Medium
- **Impact:** malformed `all_of`/`any_of` trees with non-dict children could bypass intended gating semantics due to filtered generator evaluation.
- **Evidence path:** `_check_activation_condition` in signaling composite branches.
- **Resolution:** fail-closed hardening for malformed composite `conditions` payloads (must be non-empty list of dict nodes).
- **Patched files:**
  - `src/phids/engine/systems/signaling.py`
  - `tests/test_coverage_gaps.py`

### 3) Termination parity between world scans and shared tick metrics needed broader guardrails (Fixed)

- **Severity:** Medium
- **Impact:** regressions in `check_termination` dual-path behavior could produce divergent termination reasons depending on call site.
- **Evidence path:** `check_termination(..., tick_metrics=...)` vs scan-based path in `src/phids/telemetry/conditions.py`.
- **Resolution:** added branch-matrix parity tests across Z2/Z3/Z4/Z5/Z6/Z7 and precedence scenarios.
- **Patched files:**
  - `tests/unit/telemetry/test_termination_conditions.py`
  - `tests/integration/systems/test_termination_and_loop.py`

### 4) Dashboard hot-path benchmark had no explicit budget assertions (Fixed)

- **Severity:** Medium
- **Impact:** performance regressions in `build_live_dashboard_payload` plus JSON serialization could pass unnoticed when only trend output is inspected.
- **Resolution:** added explicit warning/fail latency budgets (env-overridable) in the benchmark test.
- **Patched file:**
  - `tests/benchmarks/test_dashboard_payload_benchmark.py`

### 5) `/ws/ui/stream` first-frame contract needed stronger wire-level parity checks (Fixed)

- **Severity:** Low
- **Impact:** subtle drift between presenter output and websocket wire payload could go undetected despite key/column checks.
- **Resolution:** integration assertion now compares first-frame core schema fields against `build_live_dashboard_payload(...)` output.
- **Patched file:**
  - `tests/integration/api/test_api_builder_and_helpers.py`

## Quick-Wins Patch Set Completed

- Stream state revision token and signature wiring.
- Signaling composite activation hardening.
- Termination parity matrix tests in unit and integration layers.
- Benchmark budget assertions for dashboard hot path.
- Websocket first-frame presenter parity checks.

## Residual Risks

1. Mutation-resistance depth remains uneven outside the covered termination and interaction pilots.
2. `/ws/ui/stream` now exposes `contract_version`, but documentation-to-schema parity still requires explicit drift guards.
3. Performance budgets currently cover dashboard build/encode mean latency; they do not yet enforce percentile-based bounds.

## Next Actions

1. Expand mutation pilot coverage to `src/phids/engine/systems/interaction.py` and `src/phids/engine/core/flow_field.py`.
2. Maintain additive-change policy checks around `/ws/ui/stream` `contract_version` evolution.
3. Introduce optional percentile budget checks for dashboard benchmark if CI/runtime variance remains stable.
