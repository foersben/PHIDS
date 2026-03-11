# Development and Documentation Standards

This section governs how PHIDS should be extended without violating its scientific or
architectural commitments.

It is written for contributors who need to understand not only *how to run checks*, but also *how
to make changes without breaking the simulator’s methodological guarantees*.

## Canonical Development Chapter

- [`contribution-workflow-and-quality-gates.md`](contribution-workflow-and-quality-gates.md)
- [`documentation-status-and-open-work.md`](documentation-status-and-open-work.md)
- [`github-actions-and-local-ci.md`](github-actions-and-local-ci.md)
- [`documentation-standards.md`](documentation-standards.md)
- [`testing-strategy-and-benchmark-policy.md`](testing-strategy-and-benchmark-policy.md)

## Non-Negotiable Engineering Principles

- data-oriented design over ad-hoc object graphs,
- vectorized NumPy state for environmental layers,
- strict respect for double-buffering boundaries,
- Rule-of-16 memory discipline,
- Numba on hot-path numerical kernels,
- O(1) spatial locality queries,
- research-grade reproducibility and test coverage.

These rules are not merely style preferences. They are part of the current scientific and runtime
identity of PHIDS.

## Quality Gates

The current repository quality gates include:

- Ruff linting and formatting,
- mypy static checking,
- pytest with coverage and benchmarks,
- strict MkDocs build validation.

## Who This Section Is For

This section is most useful for:

- contributors changing engine behavior,
- contributors changing the draft/UI workflow,
- contributors extending scenario semantics,
- contributors working on telemetry, replay, and export surfaces,
- contributors expanding canonical documentation.

## Documentation Standards

Canonical documentation should:

- be formal and precise,
- distinguish current behavior from planned behavior,
- link prose to concrete modules and symbols,
- cite legacy provenance during migration,
- remain buildable under `mkdocs build --strict`.

## Practical Focus

The development documentation emphasizes:

- edit ownership by subsystem,
- draft-vs-live state boundaries,
- explicit documentation handoff notes for deferred work,
- focused vs full quality-gate selection,
- GitHub Actions structure and local rehearsal before pushing,
- benchmark-triggering classes of changes,
- CI parity and documentation discipline.

## Key Inputs

- `AGENTS.md`
- `.github/copilot-instructions.md`
- `pyproject.toml`
- `legacy/2026-03-11/docstring_guidelines.md`
- `legacy/2026-03-11/technical_requirements.md`
