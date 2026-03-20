# Agent Ownership and Delegation

This chapter defines ownership boundaries and delegation contracts for PHIDS agents so that documentation, repository operations, and verification work remain auditable and non-overlapping. The objective is to make routing decisions deterministic: each task type should have a primary owner, explicit handoff payload requirements, and a clear QA authority.

The ownership model is intentionally asymmetric. Documentation coordination is centralized in `docs-librarian`; narrative writing is delegated by domain and writing mode; repository publication is centralized in `git-ops`; and test-failure recovery is centralized in `test-ops`. This separation limits policy drift and reduces cross-surface regressions.

## Ownership Matrix

| Agent | Primary Ownership | Typical Inputs | Required Outputs | QA Recipient |
|---|---|---|---|---|
| `docs-librarian` | Documentation IA, delegation, final docs QA | Task scope, target files, writing-mode requirements | Accepted/rejected docs outcome with evidence | User |
| `docs-scientist` | Scientific and algorithmic docs content | Librarian-assigned files, scientific context | Formal prose and diagrams grounded in implementation | `docs-librarian` |
| `docs-operator` | Operational runbooks and contributor procedures | Librarian-assigned files, workflow context | Reproducible guidance and command flows | `docs-librarian` |
| `docs-annotator` | Python docstring-only updates | Target Python modules/tests | Docstring diffs only, no logic changes | Requesting coordinator |
| `git-ops` | Git lifecycle actions and publication workflows | Branch context, staged slices, operator authorization | Commits/refs/PR state and verification notes | User |
| `test-ops` | Test triage, recheck, coverage recovery | Failing command output, changed files | Recheck bundle with pass/fail and residual risk | `git-ops` or User |

## Delegation Defaults

- Engine/foundations and analytical reference narratives route to `docs-scientist`.
- Runbooks, CI/CD, contributor workflow pages route to `docs-operator`.
- Python docstring-only tasks route to `docs-annotator`.
- Git publication or branch lifecycle tasks route to `git-ops`.
- Failing tests, flake triage, and coverage recovery route to `test-ops`.

## Handoff Contract

Every delegated task should include:

1. Explicit file targets.
2. Intended writing mode or operational objective.
3. Acceptance criteria (for example, nav registration, evidence references, or test command results).
4. Required verification command if a build/test gate is expected.

Every delegated result should include:

1. Findings-first status.
2. Concrete file references.
3. Evidence of tool-backed checks or explicit blocked actions.
4. Residual risks and required next gate.

## Escalation and Retasking

If delegated output is incomplete, off-surface, or evidence-light, the coordinator retasks with explicit correction criteria. If tool access is blocked, the agent reports fail-closed status and provides exact reproduction commands rather than claiming completion.

## Review Responsibilities

- `docs-librarian` performs final docs QA for structure, style-mode fit, nav/link integrity, and implementation truth.
- `git-ops` resumes publish flow only after required verification returns from `test-ops` when test gates fail.
- User approval remains the final authority for remote-impacting actions and publication decisions.

## Summary

Ownership and delegation in PHIDS are designed to minimize ambiguity. Each agent has a bounded remit, each handoff has required payload structure, and each closure requires evidence. This preserves consistency across documentation quality, repository lifecycle operations, and deterministic test validation.
