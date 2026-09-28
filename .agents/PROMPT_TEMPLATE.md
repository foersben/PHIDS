---
type: Reference
title: Jules Standard Prompt Appendix
status: stable
stale_after: "2027-06-01T00:00:00Z"
version: 1.1
description: >
  Copy-paste prompt appendix for Jules sessions. Prevents aggressive directory
  crawling, clarifies commit signing vs GitHub Web-Flow, and enforces path-scoped
  role selection from the first token.
tags: [agents, jules, prompt-template, token-guardrail]
generated: {by: process:agent-config-refactor, at: "2026-09-28T00:00:00Z"}
---

# Jules Standard Prompt Appendix

Append the guardrail block below to any Jules task description.

---

## Universal Guardrail Block

```text
MCP Guidance & Token Guardrails:
* Read AGENTS.md at the repo root. Then open .agents/index.md.
* Use the decision matrix in .agents/index.md to select your role.
* Sub-directory AGENTS.md files load automatically; do not skip them.
* Do NOT run generic directory listings (ls, find) across .agents/.
* Load only the role file (.agents/roles/) for the paths you are modifying.
* Do NOT open .agents/memory/ or .agents/manifesto/ unless explicitly requested.
* All Python: uv run or just only. Never bare python, pip, or poetry.
* Never run act commands in sandbox; act requires a local workstation Docker daemon.
* Commits & PRs: Push PR feature branch directly. Do not run git commit -S (signing occurs upon PR merge via GitHub Web-Flow).
* If touching engine/systems/ or api/schemas/, run gates before committing:
    uv run python scripts/audit_matrix_coverage.py
    uv run python scripts/verify_matrix_trace_parity.py --all
    uv run mypy src/phids
```

---

## Canned Variant: Complexity Agent

```text
Task: Run the cognitive complexity audit and refactor ONE function scoring
above 15 (or near threshold 12-15). Balance complexity reduction against performance risk.

MCP Guidance & Token Guardrails: [paste universal block]

Complexity-specific constraints:
* Scan with: just complexity (or uvx complexipy . --sort desc)
  (Do NOT run act-complexity or act -j cognitive-complexity; Docker is unavailable)
* Read .agents/memory/complexity.md for prior learnings before selecting target.
* If no functions exceed 15: inspect near-threshold candidates (12 <= score <= 15).
  If all functions are cleanly under 12, record compliance in memory and exit cleanly without creating a PR.
* If target is in engine/systems/, also load .agents/rules/02-numba-constraints.md.
* Never extract helper functions inside @njit functions (Numba cannot JIT closures).
* Benchmark gate: uv run pytest tests/benchmarks/ - do not PR if >5% regression.
* Verification: uv run ruff format . && uv run ruff check . && uv run mypy src/phids && uv run pytest
```

---

## Canned Variant: Chisel Agent

```text
Task: Identify ONE monolith or mixed-responsibility module and refactor it
into a clean sub-package. Remove all backwards-compat shims.

MCP Guidance & Token Guardrails: [paste universal block]

Chisel-specific constraints:
* Read .agents/memory/chisel.md for prior learnings before scanning.
* Find large files without a full crawl:
    uv run python -c "import os,glob; [print(f'{os.path.getsize(p):>8} {p}') for p in glob.glob('src/**/*.py', recursive=True) if os.path.getsize(p) > 12000]"
* NEVER split engine/core/ or engine/systems/ without reading
  .agents/rules/02-numba-constraints.md AND .agents/rules/01-stochastic-engine-and-replay.md first.
* NEVER add class attributes/instance variables to engine components.
  ECS components are NumPy arrays. OOP in engine core is banned.
* Verification: uv run ruff format . && uv run ruff check . && uv run mypy src/phids && uv run pytest
* If touching schemas/systems: run uv run python scripts/audit_matrix_coverage.py
```

---

## Canned Variant: Bolt Agent

```text
Task: Identify ONE measurable performance opportunity and implement it.
Benchmark against develop before creating a PR.

MCP Guidance & Token Guardrails: [paste universal block]

Bolt-specific constraints:
* Read .agents/memory/bolt.md for prior learnings. Do not revisit explored targets.
* Check these known remaining opportunities first (highest ROI):
    1. np.any(layer >= SIGNAL_EPSILON) in biotope.py -> replace with .max() >= SIGNAL_EPSILON
    2. In-loop dynamic imports in movement/core.py and movement/incidental.py
    3. Non-short-circuiting accumulator in @njit anchoring.py search loop
* NEVER change write-layer shape or Zarr chunk layout without running:
    uv run pytest tests/integration/telemetry/
* Float mask mandate: @njit state transitions must use 0.0/1.0 float masks,
  never if/else branches inside hot paths.
* Benchmark: just bench-compare-jit develop worktree examples/rectangular_crossfire_extended.json 100 10 10
  Fallback if just unavailable: uv run pytest tests/benchmarks/ --benchmark-compare
```

---

## Usage Pattern

1. Copy the Universal Guardrail Block.
2. If a periodic agent session, also copy the relevant Canned Variant.
3. Paste both BEFORE your task description in the Jules task prompt field.
