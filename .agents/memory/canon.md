---
type: memory
title: "Canon Memory"
---

## 2026-08-04 - Documentation Integrity Audit

Learning: Identified legacy mkdocs terminology and outdated test paths lingering in roadmap and traceability files. Zensical is strict about resource paths matching physical files.
Action: When refactoring file structures or migrating toolchains, always execute a global search across docs/ for stale legacy toolchain references and broken resource links.

## 2025-02-18 - [Verification of Codebase State Before Proposing Changes]

Learning: [When acting as an alignment agent (like 'Canon') to fix documentation-to-code drift, it's critical to explicitly verify the *current* state of the codebase (e.g., reading the Pydantic schemas and engine loops directly) before proposing changes, to avoid hallucinating discrepancies that have already been resolved. The context provided initially may be stale.]
Action: [Before identifying any drift between docs and code, write commands to fully read the relevant code modules (`schemas.py`, `feeding.py`, etc.) to prove the drift exists. Never assume the current code state without checking.]

## 2026-08-05 - [Documentation Re-organization and Path Validation]

Learning: [When performing large structural re-organizations of Markdown documentation (like renaming or merging sub-folders like `speculative_research` into nested domains), Zensical builds will silently succeed if internal markdown links refer to non-existent paths, but standard `build` diagnostics might catch them depending on config. A recursive regex or `grep` is essential to identify and fix stale relative paths (e.g. `../speculative_research`) before committing.]
Action: [Always perform a recursive `grep` for the old directory name (`grep -rn 'old_folder' docs/`) across the entire `docs/` folder, and iteratively use `sed` to update all internal links. After updating, rigorously check the generated site using `uv run zensical build -f zensical.toml` and manually inspect for `page does not exist` warnings.]

## 2026-07-26 - [Documentation Escaping]

Learning: When using multi-line Python strings to inject LaTeX code (e.g. `\approx`, `\%`, `\c`, `\g`) into markdown files, standard Python string parsing interprets backslash sequences as literal escape codes. This causes `SyntaxWarning: invalid escape sequence` and silent corruption of the text (e.g., `\a` becoming an ASCII bell character, breaking math rendering). Action: Always use raw string literals (`r"""..."""`) in Python scripts designed to edit or generate markdown containing LaTeX, or explicitly double-escape the backslashes to preserve macro integrity.

## 2026-08-14 - [OKF Data-Flow Matrix Modeling Mandate]

Learning: Modeling complex multi-tick causal behavioral cascades with scalar enums or if/else branches breaks SIMD vectorization and introduces hidden state drift.
Action: All multi-tick behavioral cascades must be modeled as an OKF Data-Flow Matrix table in documentation before implementation, and verified with corresponding Pytest time-series trace tests.
## 2026-08-15 - [Documentation Compliance] Learning: Mass OKF upgrades (v0.1 to v0.2) required automated script pipelines to handle widespread tag lists (`tags: [tag1, tag2]`) and replaced `timestamp:` with `generated: { by: process:okf-updater, at: <time> }` to conform precisely to the v0.2 specifications. Action: Use strict format regex when migrating documentation headers and rely on `.agents/` workflow compliance scripts (`scripts/validate_okf.py`) to systematically assert graph continuity and schema integrity.
