---
type: concept
title: "Test Suite Taxonomy"
status: active
version: 1.0
description: "Overview of the PHIDS test suite architecture and execution lanes."
---

# Test Suite Taxonomy & Execution Topography

The PHIDS testing rig is architecturally partitioned into five distinct lanes, mapping the flow of data from property-invariant validation to live transport stream resilience. This layered defense ensures that computational rules align with the biological model, data structures gracefully serialize, and the engine correctly protects constraints (e.g., the Rule of 16).

- **Unit Telemetry and Data Engineering:** Found in `tests/unit/telemetry/`, tests here ensure that Polars DataFrames correctly reflect cross-tick invariants. E.g., handling zeros correctly for absent species, preserving flat column paradigms over nested dicts, and maintaining data correctness.
- **Integration API and HTTP Boundaries:** Defined largely within `tests/integration/api/`, these tests enforce the outer perimeter. They ensure malformed payloads return specific (400, 422, 404) explicit HTTP codes before polluting internal state, validate type-coercion behaviors on builder routes, and protect hard limits like the maximum of 16 branches (Rule of 16).
- **Property Invariants and Mathematics:** Managed within `tests/integration/systems/test_interaction_property_invariants.py`. These run deterministic, bounded parameterized loops enforcing exact closed-form solutions for metabolic attrition, reproduction bounds, and monotonic behaviors regarding populations and baseline energy.
- **Hypothesis and Mutation Pilot Lanes:** Found in `tests/integration/systems/test_interaction_mutation_pilot.py` and `test_interaction_hypothesis_pilot.py`. These pilots use random-walk crowding boundaries, test edge cases (like 0 velocity floors or precise survival boundaries), and use Hypothesis-generated sequences to ensure constraints hold unconditionally under bounded inputs.
- **Performance Budgets and Websockets Transport:** Asserted under `tests/benchmarks/` and `tests/integration/api/test_websocket_manager.py`. These bounds verify deterministic, environment-overridable millisecond limits for specific hotspots (like diffusion flow fields or websocket payload generation) using `pytest-benchmark`. In addition, WebSockets verify graceful teardown, snapshot cache reuse for unchanged ticks, and resilience to client disconnection.
