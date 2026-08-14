---
type: Agent Workflow
title: Automated Matrix Drift Reconciliation
status: stable
stale_after: "2027-01-01"
version: 1.0
description: Automated workflow for detecting, reconciling, and updating
  documented Data-Flow Matrices when engine parameters or telemetry drift.
tags: [workflow, data-flow-matrix, drift, reconciliation]
generated: {by: process:okf-updater, at: "2026-08-14T00:30:00Z"}
verified: {by: process:okf-updater, at: "2026-08-14T16:00:00Z"}
sources:
- id: okf_data_flow_matrices
  resource: docs/development_guide/okf_data_flow_matrices.md
---

# Sequence

1. **Drift Detection (`@causal-verifier`):** Detect numerical drift between simulation telemetry trace and documented Markdown matrix tables during background CI or DSE runs.
2. **Candidate Diff Generation (`@matrix-auditor`):** Execute skill `auto-reconcile-matrix-drift` to capture the new trace output and generate an updated Markdown table diff.
3. **Review & Alignment (`@orchestrator`):** Present the reconciled table diff to the user for explicit approval.
4. **Git Sign & Commit (`@git-operator`):** Commit and push the approved specification update with a GPG-signed commit.
