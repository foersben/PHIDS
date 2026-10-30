---
name: doc-synchronization-pipeline
type: Agent Skill
title: Documentation & README Synchronization Pipeline
status: stable
stale_after: "2027-01-01T00:00:00Z"
version: 1.0.0
description: Multi-phase audit and synchronization pipeline for detecting, triaging, and updating workspace READMEs and Zensical documentation across code changes.
tags: [workflow, documentation, zensical, okf, readme, parity]
generated: {by: process:agent-os-refactor, at: "2026-10-30T00:00:00Z"}
verified: {by: process:agent-os-refactor, at: "2026-10-30T00:00:00Z"}
sources:
- id: agents_master
  resource: AGENTS.md
- id: validate_okf
  resource: scripts/validate_okf.py
- id: audit_matrix_coverage
  resource: scripts/audit_matrix_coverage.py
- id: verify_matrix_trace_parity
  resource: scripts/verify_matrix_trace_parity.py
---

# Documentation & README Synchronization Pipeline

A comprehensive, modular pipeline designed to eliminate documentation drift across the repository following multi-module code, schema, or algorithmic refactors. It inspects all workspace README files, audits Zensical concept documentation (`docs/`), and validates OKF invariants.

---

## Trigger

* **Slash Command:** `/doc-synchronization-pipeline`
* **Direct Triggers:**
  * After major feature additions or vertical slice merges.
  * When modifying schemas (`src/phids/api/schemas/`) or engine systems (`src/phids/engine/systems/`).
  * Prior to tagging a new release.

---

## Architectural Sequence

```mermaid
graph TD
    Trigger([Trigger: /doc-synchronization-pipeline]) --> Phase1[Phase 1: Git Diff & Documentation Impact Mapping]
    Phase1 --> Phase2{Phase 2: Modular Execution Gate}

    subgraph Tracks [Execution Tracks]
        Phase2 -->|Track A: Local Rapid Scan| LocalReadmes[Sync Workspace READMEs]
        Phase2 -->|Track B: Local Zensical Audit| LocalDocs[Audit Zensical Concept Docs]
        Phase2 -->|Track C: Sub-Workflow Trigger| DelegatedWorkflows[Trigger /validate-full-stack or /auto-reconcile-matrix-drift]
    end

    LocalReadmes --> Phase5[Phase 5: Zensical Strict Build & Verification Gate]
    LocalDocs --> Phase5
    DelegatedWorkflows --> Phase5
```

---

## Phase 1: Git Diff & Documentation Impact Mapping

1. **Inspect Modified Files:**
   Identify modified code files relative to HEAD or develop:
   ```bash
   git status --short
   git diff --name-only origin/develop...HEAD
   ```

2. **Categorize Impact:**
   * **Domain READMEs:** `src/phids/README.md`, `scripts/README.md`, `docs/README.md`.
   * **Scientific Models:** `docs/scientific_model/**/*.md`.
   * **Architecture Guides:** `docs/architecture/**/*.md`.

---

## Phase 2: Execution Tracks

### Track A: Workspace README Synchronization
* Audit each domain README against actual package structure and entry points.
* Verify command snippets use `uv run` or `just`.

### Track B: Zensical Concept Docs Audit
* Validate mathematical formulas against implemented kernels in `src/phids/engine/systems/`.
* Verify Data-Flow Matrix tables have 100% numerical parity with Pytest traces.

### Track C: Automated Parity and Coverage Checks
* Run `uv run python scripts/audit_matrix_coverage.py`.
* Run `uv run python scripts/verify_matrix_trace_parity.py --all`.

---

## Phase 3: Zensical Build & Verification Gate

Run static documentation compiler:
```bash
uv run zensical build -f zensical.toml
uv run python scripts/validate_okf.py
```
Ensure zero broken links, syntax warnings, or missing frontmatter fields.
