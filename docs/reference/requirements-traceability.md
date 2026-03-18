# Requirements Traceability

This page is the canonical current-state successor to the legacy requirements coverage notes. It maps
major PHIDS requirements to:

- the active implementation owners,
- the canonical narrative documentation,
- the strongest corroborating tests.

Its purpose is not to restate every requirement in prose, but to show where each one lives in the
current repository and documentation corpus.

## How to Read This Page

Each row answers three questions:

1. **Where is the requirement implemented?**
2. **Where is it explained canonically?**
3. **Where is it verified?**

This makes the page useful both for contributors and for readers auditing whether the current docs
still track the actual codebase.

## Core Technology and Runtime Requirements

| Requirement | Primary implementation owners | Canonical docs | Strong corroborating tests |
| --- | --- | --- | --- |
| Data-oriented ECS model | `phids.engine.core.ecs`, `phids.engine.components.*` | `docs/architecture/index.md`, `docs/engine/ecs-and-spatial-hash.md` | `tests/unit/engine/core/test_ecs_world.py`, `tests/unit/api/test_schemas_and_invariants.py` |
| NumPy-backed environmental state | `phids.engine.core.biotope` | `docs/engine/biotope-and-double-buffering.md`, `docs/foundations/index.md` | `tests/unit/api/test_schemas_and_invariants.py`, `tests/unit/engine/core/test_biotope_diffusion.py` |
| Double-buffered field updates | `GridEnvironment` in `phids.engine.core.biotope` | `docs/engine/biotope-and-double-buffering.md`, `docs/engine/index.md` | `tests/unit/api/test_schemas_and_invariants.py` |
| Rule of 16 bounded matrices/species | `phids.shared.constants`, `phids.api.schemas`, `phids.engine.core.biotope` | `docs/foundations/research-scope.md`, `docs/scenarios/schema-and-curated-examples.md`, `docs/reference/module-map.md` | `tests/unit/api/test_schemas_and_invariants.py`, `tests/e2e/scenarios/test_example_scenarios.py` |
| Numba-accelerated hot path | `phids.engine.core.flow_field` | `docs/engine/flow-field.md` | `tests/unit/engine/core/test_flow_field.py`, `tests/benchmarks/test_flow_field_benchmark.py` |
| Subnormal float truncation | `SIGNAL_EPSILON` use in `phids.engine.core.biotope` | `docs/engine/biotope-and-double-buffering.md` | `tests/unit/engine/core/test_biotope_diffusion.py` |
| O(1)-style spatial locality queries | `phids.engine.core.ecs` and its consumers in `interaction` / `signaling` | `docs/engine/ecs-and-spatial-hash.md`, `docs/engine/interaction.md`, `docs/engine/signaling.md` | `tests/unit/engine/core/test_ecs_world.py`, `tests/benchmarks/test_spatial_hash_benchmark.py`, `tests/unit/api/test_schemas_and_invariants.py` |
| Global unified pathfinding gradient | `phids.engine.core.flow_field`, consumed by `phids.engine.systems.interaction` | `docs/engine/flow-field.md`, `docs/engine/interaction.md` | `tests/unit/engine/core/test_flow_field.py`, `tests/benchmarks/test_flow_field_benchmark.py` |

## Interface and Control Requirements

| Requirement | Primary implementation owners | Canonical docs | Strong corroborating tests |
| --- | --- | --- | --- |
| Validated scenario ingress | `phids.api.schemas`, `phids.io.scenario`, `phids.api.main` | `docs/scenarios/schema-and-curated-examples.md`, `docs/interfaces/rest-and-websocket-surfaces.md` | `tests/e2e/scenarios/test_example_scenarios.py`, `tests/unit/api/test_schemas_and_invariants.py`, `tests/unit/io/test_scenario_io.py`, `tests/integration/api/test_api_simulation_and_scenario_routes.py` |
| REST control surface for live simulation | `phids.api.main`, `SimulationLoop` | `docs/interfaces/rest-and-websocket-surfaces.md`, `docs/architecture/index.md` | `tests/integration/api/test_api_routes.py`, `tests/integration/api/test_api_simulation_and_scenario_routes.py` |
| Distinct draft vs live state ownership | `phids.api.ui_state`, `phids.api.main`, `SimulationLoop` | `docs/ui/draft-state-and-load-workflow.md`, `docs/interfaces/index.md` | `tests/unit/api/test_ui_state.py`, `tests/integration/api/test_ui_routes.py`, `tests/integration/api/test_api_builder_and_helpers.py` |
| Server-rendered HTMX/Jinja UI | `phids.api.main`, `phids.api.ui_state`, `src/phids/api/templates/` | `docs/ui/index.md`, `docs/ui/htmx-partials-and-builder-routes.md` | `tests/integration/api/test_ui_routes.py`, `tests/integration/api/test_api_builder_and_helpers.py` |
| Binary simulation WebSocket stream | `/ws/simulation/stream` in `phids.api.main` | `docs/interfaces/rest-and-websocket-surfaces.md` | `tests/integration/api/test_api_builder_and_helpers.py`, `tests/integration/api/test_api_routes.py` |
| Lightweight UI WebSocket stream | `/ws/ui/stream` in `phids.api.main` | `docs/interfaces/rest-and-websocket-surfaces.md`, `docs/ui/index.md` | `tests/integration/api/test_api_builder_and_helpers.py`, `tests/integration/api/test_api_routes.py` |

## Scenario and Trigger-Language Requirements

| Requirement | Primary implementation owners | Canonical docs | Strong corroborating tests |
| --- | --- | --- | --- |
| `SimulationConfig` as executable experiment boundary | `phids.api.schemas`, `phids.io.scenario` | `docs/scenarios/schema-and-curated-examples.md`, `docs/scenarios/scenario-authoring-and-trigger-semantics.md` | `tests/e2e/scenarios/test_example_scenarios.py`, `tests/unit/api/test_schemas_and_invariants.py`, `tests/unit/io/test_scenario_io.py` |
| Nested trigger activation conditions | `TriggerConditionSchema`, `DraftState` helpers, `phids.engine.systems.signaling` | `docs/scenarios/scenario-authoring-and-trigger-semantics.md`, `docs/engine/signaling.md` | `tests/unit/api/test_ui_state.py`, `tests/integration/systems/test_systems_behavior.py`, `tests/unit/api/test_schemas_and_invariants.py` |
| Curated examples as a tested compatibility surface | `examples/`, `phids.io.scenario`, `SimulationLoop` | `docs/scenarios/curated-example-catalog.md`, `docs/scenarios/schema-and-curated-examples.md` | `tests/e2e/scenarios/test_example_scenarios.py` |
| Example-pack plants-plus-swarms competition rule | `examples/`, test contract in `tests/e2e/scenarios/test_example_scenarios.py` | `docs/scenarios/curated-example-catalog.md` | `tests/e2e/scenarios/test_example_scenarios.py` |

## Telemetry, Replay, and Export Requirements

| Requirement | Primary implementation owners | Canonical docs | Strong corroborating tests |
| --- | --- | --- | --- |
| Per-tick ecological summary metrics | `phids.telemetry.analytics`, `SimulationLoop` | `docs/telemetry/analytics-and-export-formats.md`, `docs/telemetry/index.md` | `tests/integration/systems/test_termination_and_loop.py`, `tests/unit/telemetry/test_telemetry_per_species.py` |
| CSV and NDJSON export surfaces | `phids.telemetry.export`, `phids.api.main` | `docs/telemetry/analytics-and-export-formats.md`, `docs/interfaces/rest-and-websocket-surfaces.md` | `tests/unit/telemetry/test_export_helpers.py`, `tests/integration/api/test_api_simulation_and_scenario_routes.py` |
| Deterministic replay snapshots | `phids.io.replay`, `SimulationLoop.get_state_snapshot`, `GridEnvironment.to_dict` | `docs/telemetry/replay-and-termination-semantics.md` | `tests/e2e/replay_and_io/test_replay_roundtrip.py`, `tests/unit/io/test_replay_buffer.py`, `tests/integration/systems/test_termination_and_loop.py` |
| Formal `Z1`–`Z7` termination semantics | `phids.telemetry.conditions`, `SimulationLoop` | `docs/telemetry/replay-and-termination-semantics.md`, `docs/telemetry/index.md` | `tests/integration/systems/test_termination_and_loop.py` |

## Quality and Documentation Requirements

| Requirement | Primary implementation owners | Canonical docs | Strong corroborating tests / checks |
| --- | --- | --- | --- |
| Ruff, mypy, pytest, MkDocs strict workflow | `pyproject.toml`, `.github/workflows/ci.yml`, `.pre-commit-config.yaml` | `docs/development/contribution-workflow-and-quality-gates.md` | CI workflow, local `uv run ...` gates |
| Google-style docstrings | `pyproject.toml`, source docstrings, repository writing guidance | `docs/development/documentation-standards.md` | contributor review, `pydocstyle` local audit |
| Canonical docs with legacy provenance preserved | `docs/`, `docs/legacy/`, `mkdocs.yml` | `docs/information-architecture.md`, `docs/development/documentation-standards.md` | `uv run mkdocs build --strict` |

## Relationship to Legacy Documents

This page supersedes the legacy role previously played by:

- `docs/technical_requirements.md`
- `docs/requirements_coverage.md`

Those documents remain preserved in the legacy/archive structure for provenance, but this page is the
canonical active traceability surface for the current documentation architecture.

## Where to Read Next

- For package ownership and codebase inventory: [`module-map.md`](module-map.md)
- For contributor-facing documentation rules: [`../development/documentation-standards.md`](../development/documentation-standards.md)
- For the scientific information architecture of the site: [`../information-architecture.md`](../information-architecture.md)
