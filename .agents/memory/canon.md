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

## 2026-07-26 - [Documentation Escaping] Learning: When using multi-line Python strings to inject LaTeX code (e.g. `\approx`, `\%`, `\c`, `\g`) into markdown files, standard Python string parsing interprets backslash sequences as literal escape codes. This causes `SyntaxWarning: invalid escape sequence` and silent corruption of the text (e.g., `\a` becoming an ASCII bell character, breaking math rendering). Action: Always use raw string literals (`r"""..."""`) in Python scripts designed to edit or generate markdown containing LaTeX, or explicitly double-escape the backslashes to preserve macro integrity.
