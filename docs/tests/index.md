---
type: concept
title: "Test Suite Architecture & Verification Rig"
status: active
version: 1.0
description: "Documentation detailing the PHIDS test suite architecture and verification processes."
---

# Test Suite Architecture & Verification Rig
---

### 1. Test Suite Taxonomy & Execution Topography

The PHIDS testing rig is architecturally partitioned into five distinct lanes, mapping the flow of data from property-invariant validation to live transport stream resilience. This layered defense ensures that computational rules align with the biological model, data structures gracefully serialize, and the engine correctly protects constraints (e.g., the Rule of 16).

- **Unit Telemetry and Data Engineering:** Found in `tests/unit/telemetry/`, tests here ensure that Polars DataFrames correctly reflect cross-tick invariants. E.g., handling zeros correctly for absent species, preserving flat column paradigms over nested dicts, and maintaining data correctness.
- **Integration API and HTTP Boundaries:** Defined largely within `tests/integration/api/`, these tests enforce the outer perimeter. They ensure malformed payloads return specific (400, 422, 404) explicit HTTP codes before polluting internal state, validate type-coercion behaviors on builder routes, and protect hard limits like the maximum of 16 branches (Rule of 16).
- **Property Invariants and Mathematics:** Managed within `tests/integration/systems/test_interaction_property_invariants.py`. These run deterministic, bounded parameterized loops enforcing exact closed-form solutions for metabolic attrition, reproduction bounds, and monotonic behaviors regarding populations and baseline energy.
- **Hypothesis and Mutation Pilot Lanes:** Found in `tests/integration/systems/test_interaction_mutation_pilot.py` and `test_interaction_hypothesis_pilot.py`. These pilots use random-walk crowding boundaries, test edge cases (like 0 velocity floors or precise survival boundaries), and use Hypothesis-generated sequences to ensure constraints hold unconditionally under bounded inputs.
- **Performance Budgets and Websockets Transport:** Asserted under `tests/benchmarks/` and `tests/integration/api/test_websocket_manager.py`. These bounds verify deterministic, environment-overridable millisecond limits for specific hotspots (like diffusion flow fields or websocket payload generation) using `pytest-benchmark`. In addition, WebSockets verify graceful teardown, snapshot cache reuse for unchanged ticks, and resilience to client disconnection.

### 2. System Mapping & Test Relations

```mermaid
graph TD
    %% Source Modules
    subgraph Engine["Core Simulation Engine"]
        Interaction["Interaction System"]
        Signaling["Signaling & Diffusion"]
        Lifecycle["Lifecycle & Mitosis"]
    end

    subgraph Boundaries["API & Transport Layers"]
        API["FastAPI Routes & UI Config"]
        WebSockets["WebSocket Managers"]
    end

    subgraph Telemetry["Data & Export"]
        DF["Polars DataFrame Gen"]
        Export["CSV / NDJSON Export"]
    end

    %% Test Paths
    subgraph Mathematical_Validation["Property Validation (Math Invariants)"]
        PropTests["Parametrized Invariants (test_interaction_property_invariants.py)"]
    end

    subgraph Pilot_Lanes["Pilot Lanes (Stochastic & Mutation)"]
        Hypothesis["Hypothesis Sweeps (test_interaction_hypothesis_pilot.py)"]
        Mutation["Edge-Case Sentinels (test_interaction_mutation_pilot.py)"]
    end

    subgraph Transport_Validation["API & Contract Testing"]
        APITests["Route Type & Reject (test_api_builder_and_helpers.py)"]
        WSTests["Stream Resilience (test_websocket_manager.py)"]
        MCPTests["MCP Command Loop (test_cli_main.py)"]
    end

    subgraph Benchmarks["Performance Budgets"]
        Bench["Millisecond Execution Budgets (tests/benchmarks)"]
    end

    subgraph Data_Validation["Telemetry Integration"]
        TelemetryTests["Zero-Fill & Schema (test_telemetry_per_species.py)"]
    end

    %% Wiring
    Interaction -.-> PropTests
    Interaction -.-> Hypothesis
    Interaction -.-> Mutation
    Lifecycle -.-> PropTests
    Lifecycle -.-> Hypothesis
    Signaling -.-> Bench

    API -.-> APITests
    WebSockets -.-> WSTests
    API -.-> MCPTests

    DF -.-> TelemetryTests
    Export -.-> Bench
```

### 3. Deep-Dive Quality Analysis

#### Mathematical & Trophic Invariant Correctness
**Current Status:** Excellent.
The math checks found in `test_interaction_property_invariants.py` verify that attrition and reproduction mathematically map strictly to closed-form calculations under varying bounds. This guarantees exact conservation logic (especially via `test_mitosis_threshold_and_partition_invariants`) when partitions happen.
**Masked Detail:** The current configuration heavily tests exact equality (`==`) or tight bounds (via `pytest.approx`), but it rarely exposes the explicit mathematical boundaries of floating-point arithmetic (specifically related to the `SIGNAL_EPSILON` truncation). While some unit tests do check this, larger trophic networks might conceal slow compounding truncation drift.

#### Functional & Behavioral Completeness
**Current Status:** Good, but isolated.
The test rig effectively validates API constraints (malformed JSON, 422 triggers, Rule of 16 boundaries). The mutation pilot effectively ensures branch coverage for isolated systems (random-walk triggers, crowding caps, feeding rules).
**Masked Detail:** There is a distinct lack of deep system interaction testing representing long-term runaway ecological scenarios or long tail chain reactions (e.g., continuous multi-generational evolutionary loops or directional wind-dispersal vectors leading to permanent biotope dominance).

#### Performance Regressions & Resource Budgets
**Current Status:** Budgeted but lacking Memory Tracking.
Latency throughput tests (`tests/benchmarks/`) are robustly constrained with clear median and $p_{95}$ failing/warning thresholds explicitly configurable via environment variables (e.g., `PHIDS_DIFFUSION_SPARSE_WARN_MEAN_MS`). Tests effectively isolate specific Numba algorithms or export logic.
**Masked Detail:** There is zero instrumentation measuring memory allocation churn, `gc` impact, or deep object instantiation within inner simulation loops. The focus is entirely on runtime latency (`wall-clock`), which masks potential multi-tick memory blowups that slow down execution due to garbage collection over time.

#### Concurrency, WebSockets, & State Pollution
**Current Status:** Verified.
Stream durability is verified nicely via `test_websocket_manager.py`. It explicitly verifies missing/terminated loops behave correctly, snapshot caching limits redundant work for unchanged ticks, and tests resilience around `WebSocketDisconnect` handling.
**Masked Detail:** The integration lacks tests around actual network stress concurrent to ongoing ticks. The stream test validates explicit disconnects but does not cover race conditions when a simulation loop executes heavy writes synchronously with thousands of client subscriptions.

### 4. Testing Gaps & Vulnerabilities Register

| Area / Target Sub-system | Functional Behavior / Invariant Expected | Current Testing Limitation | Severity / Risk |
| :--- | :--- | :--- | :--- |
| **GridEnvironment & Math** | Floating Point `SIGNAL_EPSILON` precision in Trophic layers | Tightly managed in isolated units but under-asserted across massive multi-tick trophic loops where truncation compounds. | `[CRITICAL COMPLIANCE]` |
| **Simulation Core Dynamics** | Multi-Generational Sub-System Reactions | Missing tests for long-term runaway cascade reactions (e.g., irreversible defense synthesis cascading across biomes). | `[CRITICAL COMPLIANCE]` |
| **Performance Benchmarks** | Memory Allocation Churn & GC Monitoring | Benchmarks explicitly track wall-clock execution limits but lack `tracemalloc` to track allocations, masking internal memory leaks. | `[STRUCTURAL ARCHITECTURE]` |
| **API WebSockets** | Network Stalls & Asynchronous Race Conditions | No validation for transport durability when thousands of reconnections happen mid-tick, missing active stress testing. | `[STRUCTURAL ARCHITECTURE]` |
| **API Integration** | Mock System Pollution | Hardcoded UI configurations or states modified in tests may not reliably clean themselves up if not strictly guarded by fixtures, occasionally relying on default drafts. | `[QUALITY-OF-LIFE / DEVEX]` |

### 5. Ranked Strategic Recommendations

#### `[CRITICAL COMPLIANCE]`
1. **Implement Multi-Generational Trophic Cascade Assertions:** Build new integration tests that run for thousands of ticks testing compound network reactions (e.g., continuous unidirectional wind leading to complete grid colonization, ensuring mass and energy conservation holds perfectly).
2. **Global Precision Analysis:** Audit and inject specific mathematical failure thresholds testing for compounding `SIGNAL_EPSILON` drifts inside massive environment grids across large tick durations.

#### `[STRUCTURAL ARCHITECTURE]`
3. **Integrate Memory Profiling into Benchmarks:** Integrate `pytest-memray` or `tracemalloc` assertions into the current latency benchmarks to measure memory allocations strictly per-tick.
4. **WebSocket Stress Scenarios:** Implement tests simulating violent connection loss, massive concurrent connections, and network saturation during active simulation writes to protect against async loop blocking.

#### `[QUALITY-OF-LIFE / DEVEX]`
5. **Fixture & Mock System Isolation:** Move all hardcoded payload configurations inside API integration tests into centralized reusable Pytest fixtures.
