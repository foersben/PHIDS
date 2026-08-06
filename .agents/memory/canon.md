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
## 2026-08-06 - [Complexipy and Markdown Regex Escaping]

Learning: [When injecting raw LaTeX math blocks (`$$ \frac{\partial ...} $$`) into markdown via python string replacements, the backslashes can be mistakenly parsed by `re.sub` as bad regex escape sequences (e.g., `re.error: bad escape \p`), which will cause Python automation scripts to crash. Also, complexipy scanning steps in CI might get stuck or crash if documentation contains unescaped characters or formatting anomalies that break its parser.]
Action: [When inserting complex LaTeX formulas with Python's `re.sub`, always sanitize the payload string by explicitly replacing single backslashes with double backslashes `.replace('\\', '\\\\')` before insertion.]
