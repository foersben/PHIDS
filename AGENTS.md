# PHIDS Master Agent Router

<!-- UNIVERSAL AGENT CONSTRAINTS -->
* Toolchain: Execute all Python commands exclusively via `uv run` or `just`. Never bare `python`, `pip`, `uvx`, or `poetry`.
* Commits: Workstation agents MUST GPG/SSH sign (`git commit -S`). Escalate on signature failure.
* Architecture: ECS data-oriented. Components are contiguous NumPy arrays. Systems are pure functions. OOP inside engine core is banned.
* JIT & SIMD: Hot paths use Numba `@njit`. Ban Python objects (`dict`, `list`, closures) and allocations in inner loops. Float masks (0.0/1.0) only.
* Replay & Invariants: Simulation outcomes stream to Zarr replay buffers. Read from historical Zarr buffers for playback.
* Cognitive Complexity: Ceiling <= 15 (`just complexity`).

## Mandatory Pre-Commit Gates
Run before any commit to `src/phids/engine/` or `src/phids/api/schemas/`:
```bash
uv run python scripts/governance/audit_matrix_coverage.py
uv run python scripts/governance/verify_matrix_trace_parity.py --all
uv run ruff check src/ && uv run mypy src/phids
```

## Fast Module & Test Routing Map
| Domain | Path Scope | Primary Rule | Key Tests / Commands |
| :--- | :--- | :--- | :--- |
| **Engine Core & JIT** | `src/phids/engine/core/` | `02-numba-constraints.md` | `just test-parity`, `just test-replay` |
| **ECS Systems** | `src/phids/engine/systems/` | `05-data-flow-invariants.md`, `07-hardware-and-simd-invariants.md` | `just test-matrix` |
| **API & Schemas** | `src/phids/api/` | `06-clean-code-and-antipatterns.md` | `uv run pytest tests/unit/api/` |
| **Telemetry & Zarr** | `src/phids/telemetry/` | `01-stochastic-engine-and-replay.md` | `uv run pytest tests/unit/telemetry/` |
| **Documentation** | `docs/` | `04-markdown-formatting.md` | `just validate-okf` |

## On-Demand Skills & Slash Commands
Detailed runbooks reside in `.agents/skills/<name>/SKILL.md`:
* `/epistemic-soundness-audit`: 10-slice relational review of biological & HPC invariants.
* `/matrix-tdd-refactor`: Coordinated Data-Flow Matrix TDD pipeline.
* `/validate-full-stack`: Full-stack pre-commit, trace parity, and Zensical build gate.
* `/implement-scientific-model`: Adding ecological behaviors to ECS arrays.
* `/auto-reconcile-matrix-drift`: Automatic capture and update of drifted Data-Flow Matrix tables.
* `/vertical-slice-development`: Building full-stack simulation features across layers.
* `/ecs-refactor-pipeline`: Safe refactoring of cold-path modules without hot-path regressions.
* `/delegation-protocol`: Structured escalation checklist for human confirmation gates.
* `/doc-synchronization-pipeline`: Synchronization of workspace READMEs and docs.
