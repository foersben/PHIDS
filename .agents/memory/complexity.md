---
type: memory
title: Complexity
status: active
version: 0.1
description: Refactoring cognitive complexity from telemetry module and learnings
tags:
- phids
- refactor
- complexity
timestamp: "2026-07-22T13:00:00Z"
resources:
- telemetry.py
name: complexity
---

## 2026-07-22 - Refactoring Telemetry API Monolith

Learning: When resolving high cognitive complexity (score 27 to 5) in a view handler (`telemetry_chartjs_data`) that builds JSON payloads, separating the deep nested data extraction logic into pure private helpers (`_filter_telemetry_rows_for_chart` and `_extract_chart_series`) dramatically flattens the view handler while posing zero execution risk to the engine loops. Benchmark tests demonstrate that keeping the exact same Numba-independent work decoupled preserves performance properties while vastly improving readability and maintainability.

Action: Isolate array filtering and iteration logic from HTTP response formatting into private functions to keep view handlers structurally flat and below a complexity threshold of 15. Verify by running `complexipy` checks alongside integration tests after each structural extraction.

## 2026-07-22 - Refactoring UI State Condition Mappings

Learning: Refactoring deeply nested tree-traversal logic (`_remap_condition_references` handling polymorphic `ConditionNode` structures) into distinct leaf and group mapper functions drastically reduces cognitive complexity (from 29 to 2) with zero performance risk to the simulation hot loop. Conversely, attempting to decompose FastAPI view handlers that rely heavily on `Form(...)` annotations (like `config_trigger_rule_condition_node_update`) into smaller helpers can unexpectedly break Pydantic request validation.

Action: Prioritize refactoring pure configuration data mutation logic over HTTP endpoints bound to strict Pydantic/FastAPI `Form` annotations to avoid validation errors. When refactoring recursive tree traversals, isolate leaf-node logic and group-node traversal into separate private helpers.
