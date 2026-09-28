# PHIDS Agent Ecosystem - Algorithmic Decision Matrix

* **For MCP agents (Jules):** Use the decision matrix to select your role.
  Sub-directory `AGENTS.md` files load automatically with domain detail.
* **For human readers:** Full annotated directory index follows the matrix.

---

## Quick-Route: Identify Your Task Type

| If you are modifying... | Adopt role | Matrix gate? | Sub-AGENTS.md auto-loads? |
| --- | --- | --- | --- |
| `src/phids/engine/systems/` or `engine/core/` | `03-engine-developer` | YES | `src/phids/engine/AGENTS.md` |
| `src/phids/api/schemas/` or `api/services/` | `02-scientific-architect` | YES | `src/phids/api/AGENTS.md` |
| `src/phids/api/routers/` or `api/presenters/` or `templates/` | `07-api-and-ui-developer` | NO | `src/phids/api/AGENTS.md` |
| `tests/` | `04-qa-automator` | YES (matrix tests) | - |
| `docs/` | `05-docs-librarian` | NO | `docs/AGENTS.md` |
| `.agents/` | `05-docs-librarian` | NO | - |
| `scripts/` | `04-qa-automator` | NO | - |
| `.github/` or `pyproject.toml` | `06-git-operator` | NO | - |
| Cross-cutting / planning | `01-orchestrator` | DEPENDS | - |
| Zarr / Polars / telemetry | `08-telemetry-and-data-engineer` | NO | - |
| Matrix coverage audit | `09-matrix-auditor` | YES | - |
| Branchless mask verification | `10-causal-verifier` | YES | - |

---

## Workflow Dispatch

| Slash Command | Workflow File | Pre-load roles |
| --- | --- | --- |
| `/epistemic-soundness-audit` | [epistemic-soundness-audit.md](workflows/epistemic-soundness-audit.md) | `02`, `09`, `10` |
| `/matrix-tdd-refactor` | [matrix-tdd-refactor.md](workflows/matrix-tdd-refactor.md) | `03`, `04`, `09` |
| `/validate-full-stack` | [validate-full-stack.md](workflows/validate-full-stack.md) | all |
| `/implement-scientific-model` | [implement-scientific-model.md](workflows/implement-scientific-model.md) | `02`, `03` |
| `/matrix-drift-reconciliation` | [matrix-drift-reconciliation.md](workflows/matrix-drift-reconciliation.md) | `09`, `10` |
| `/vertical-slice-development` | [vertical-slice-development.md](workflows/vertical-slice-development.md) | `01` + all |
| `/delegation-protocol` | [delegation-protocol.md](workflows/delegation-protocol.md) | `01` |
| `/ecs-refactor-pipeline` | [ecs-refactor-pipeline.md](workflows/ecs-refactor-pipeline.md) | `03`, `04` |
| `/jules-session-triage` | [jules-session-triage.md](workflows/jules-session-triage.md) | `01`, `04`, `06` |
| `/doc-synchronization-pipeline` | [doc-synchronization-pipeline.md](workflows/doc-synchronization-pipeline.md) | `01`, `05`, `09`, `10` |

---

## Mandatory Pre-Commit Gates

When `Matrix gate? = YES`:

```bash
uv run python scripts/audit_matrix_coverage.py
uv run python scripts/verify_matrix_trace_parity.py --all
uv run pytest tests/integration/scientific_invariants/test_causal_data_flow_matrices.py
uv run ruff check src/ && uv run mypy src/
```

---

## MCP Tool Priority

| Task | Use MCP tool (not grep/find) |
| --- | --- |
| Simulation state | `runtime_snapshot` |
| Batch job status | `query_batch_jobs` |
| Diagnostic logs | `query_diagnostic_logs` |
| Telemetry schema | `inspect_telemetry_schema` |
| Config / draft | `phids://config/draft.json` |

---

## Restricted Memory Policy

Load ONLY when the user explicitly requests:

| Resource | Trigger keyword |
| --- | --- |
| `.agents/memory/bolt.md` | "HPC", "performance history", "benchmark learnings" |
| `.agents/memory/chisel.md` | "refactor history", "modularization learnings" |
| `.agents/memory/canon.md` | "canon", "milestones" |
| `.agents/memory/complexity.md` | "complexity history" |
| `.agents/memory/palette.md` | "UI history", "design decisions" |
| `.agents/memory/architecture_state_map.md` | "system topology", "full architecture" |
| `.agents/manifesto/phids-core-philosophy.md` | "manifesto", "historical" |

---

## Autonomous Agent Ecosystem Directory

This directory houses the autonomous agent architecture, role specializations, hard behavioral constraints (rules), operational workflows, executable skills, and collective memory for the Plant-Herbivore Interaction & Defense Simulator (PHIDS).

---

## Foundation & Guidelines

* [Welcome & Ecosystem Overview](README.md) - Architectural overview of decoupled AI specialization and jurisdictional separation of concerns.
* [Agent Routing & Core Constraints](AGENTS.md) - Master routing table defining team triggers, ECS constraints, double-buffering invariants, and continuous synchronization protocols.
* [Core Philosophy Manifesto](manifesto/phids-core-philosophy.md) - Foundational computational ecology vision and data-oriented design philosophy.

---

## Agent Roles

* [01 - Orchestrator](roles/01-orchestrator.md) - Project manager coordinating multi-agent initiatives, task decomposition, and structural validation.
* [02 - Scientific Architect](roles/02-scientific-architect.md) - Mathematical modeler translating reaction-diffusion PDEs, chemotactic fields, and biological invariants.
* [03 - Engine Developer](roles/03-engine-developer.md) - High-performance computing engineer maintaining ECS arrays, Numba `@njit` kernels, and double-buffered layers.
* [04 - QA Automator](roles/04-qa-automator.md) - Test engineer isolating edge cases, running mutation suites (`mutmut`), and asserting invariant coverage.
* [05 - Docs Librarian](roles/05-docs-librarian.md) - Technical writer maintaining Open Knowledge Format (OKF) metadata, Zensical pages, and LaTeX equations.
* [06 - Git Operator](roles/06-git-operator.md) - Release engineer managing GPG-signed commits, feature branches, semantic versioning, and changelogs.
* [07 - API & UI Developer](roles/07-api-and-ui-developer.md) - Web engineer managing FastAPI routes, HTMX views, Canvas visualizers, and server-side DraftState.
* [08 - Telemetry & Data Engineer](roles/08-telemetry-and-data-engineer.md) - Data engineer maintaining Zarr replay buffers, Polars analytical exports, and deterministic playback.
* [09 - Matrix Auditor](roles/09-matrix-auditor.md) - Quality auditor verifying Data-Flow Matrix coverage and bilateral OKF documentation links.
* [10 - Causal Verifier](roles/10-causal-verifier.md) - Formal verifier asserting branchless SIMD masks and numerical table-to-trace parity.

---

## Behavioral Rules

* [Rule 00 - Python Modernization](rules/00-python-modernization.md) - Mandatory use of `uv run`, strict `mypy` typing, and `ruff` linting/formatting.
* [Rule 01 - Stochastic Engine & Replay](rules/01-stochastic-engine-and-replay.md) - Invariants for tick-by-tick Zarr serialization, engine-bypassing playback, and double-buffering.
* [Rule 02 - Numba Constraints](rules/02-numba-constraints.md) - Strict ban on Python collections in `@njit`, pre-allocation in write buffers, and float mask state transfers.
* [Rule 03 - Git Security & Signing](rules/03-git-security-and-signing.md) - Mandatory GPG/SSH cryptographic signing on all commits.
* [Rule 04 - Markdown Formatting](rules/04-markdown-formatting.md) - Standards for ASCII hyphens, typography, and clean document layouts.
* [Rule 05 - Data-Flow Invariants](rules/05-data-flow-invariants.md) - Mandatory table-to-trace parity, branchless SIMD masks, bilateral OKF linking, and continuous sync gates.

---

## Operational Workflows

* [Delegation Protocol](workflows/delegation-protocol.md) - Step-by-step checklist for human escalation when autonomous agents encounter structural barriers.
* [Implement Scientific Model](workflows/implement-scientific-model.md) - Formal pipeline for introducing new biological mechanisms from ODEs/PDEs to SIMD ECS kernels.
* [Matrix Drift Reconciliation](workflows/matrix-drift-reconciliation.md) - Automated detection and updating of Data-Flow Matrices when engine kinetics intentionally drift.
* [Matrix TDD Refactor](workflows/matrix-tdd-refactor.md) - Test-driven development loop translating matrix tables into Pytest traces and JIT kernels.
* [Validate Full-Stack Integrity](workflows/validate-full-stack.md) - Coordinated full-stack verification pipeline covering OKF, matrix coverage, parity, and Zensical builds.
* [Vertical Slice Development](workflows/vertical-slice-development.md) - End-to-end coordinated pipeline for building full-stack simulation features across all layers.
* [Documentation & README Synchronization Pipeline](workflows/doc-synchronization-pipeline.md) - Multi-phase audit and synchronization pipeline for detecting, triaging, and updating workspace READMEs and Zensical documentation across code changes, with an optional triple-parallel Jules cloud dispatch.

---

## Executable Skills

* [Analyze Zarr Telemetry](skills/analyze-zarr/SKILL.md) - Skill for inspecting and validating multi-species Zarr replay stores.
* [Audit OKF Matrix Coverage](skills/audit-okf-matrix-coverage/SKILL.md) - Automated scanning of scientific model docs for temporal state-shift coverage.
* [Auto Reconcile Matrix Drift](skills/auto-reconcile-matrix-drift/SKILL.md) - Automated reconciliation of documented tables against live trace arrays.
* [Run Benchmarks](skills/run-benchmarks/SKILL.md) - Performance benchmarking with `pytest-benchmark` regression thresholds.
* [Validate Open Knowledge Format](skills/validate-okf/SKILL.md) - Verification of OKF v0.2 frontmatter schemas and knowledge graph link integrity.
* [Verify Matrix Trace Parity](skills/verify-matrix-trace-parity/SKILL.md) - Numerical assertion of 1:1 table-to-trace parity for Data-Flow Matrices.
* [Visualize Open Knowledge Format](skills/visualize-okf/SKILL.md) - Interactive Cytoscape.js knowledge graph generator and dependency visualizer.

---

## Agent Memory & Learning Journals

* [Architecture State Map](memory/architecture_state_map.md) - Living topological map of module boundaries and dependency flows.
* [Bolt's Performance Journal](memory/bolt.md) - HPC optimization learnings, single-component fast-paths, and cache locality techniques.
* [Canon Archive](memory/canon.md) - Authoritative project milestones, design decisions, and invariant records.
* [Chisel's Refactoring Journal](memory/chisel.md) - Modularization lessons from presenter and service monolith extractions.
* [Complexity Management](memory/complexity.md) - Cognitive complexity reduction patterns and private helper extraction rules.
* [Palette's UI Journal](memory/palette.md) - Frontend design guidelines, HTMX reactive patterns, and accessibility standards.
