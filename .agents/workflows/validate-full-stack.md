---
type: Agent Workflow
title: Validate Full-Stack Integrity
status: stable
stale_after: "2027-01-01T00:00:00Z"
version: 1.0
description: Coordinated pipeline running all pre-commit gates, OKF compliance, matrix trace parity, and Zensical documentation build.
tags: [workflow, testing, validation, pre-commit, zensical, okf]
generated: {by: process:okf-updater, at: "2026-09-06T23:00:00Z"}
verified: {by: process:okf-updater, at: "2026-09-06T23:00:00Z"}
sources:
- id: validate_okf
  resource: scripts/validate_okf.py
- id: audit_matrix_coverage
  resource: scripts/audit_matrix_coverage.py
- id: verify_matrix_trace_parity
  resource: scripts/verify_matrix_trace_parity.py
---

# Sequence

1. **OKF Compliance & Graph Integrity (`@docs-librarian`):** Run `uv run python scripts/validate_okf.py` to assert YAML frontmatter schema compliance and graph link resolution across `docs/` and `.agents/`.
2. **Data-Flow Matrix Coverage Audit (`@matrix-auditor`):** Run `uv run python scripts/audit_matrix_coverage.py --dir docs/scientific_model/` to confirm all multi-tick behavioral cascades have documented matrix tables and bilateral test links.
3. **Table-to-Trace Parity Gate (`@causal-verifier`):** Run `uv run python scripts/verify_matrix_trace_parity.py --all` to assert exact numerical parity against runtime simulation trace fixtures.
4. **Licensing & IP Clean Zone (`@git-operator`):** Run `uv run python scripts/check_no_extended_imports.py` to prevent commercial licensing contamination in the core simulation engine.
5. **Static Documentation Build (`@docs-librarian`):** Run `uv run zensical build -f zensical.toml` to verify zero missing links, syntax warnings, or pymdownx rendering errors.
