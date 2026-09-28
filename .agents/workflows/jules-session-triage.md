---
type: Agent Workflow
title: Jules Session & Task Triage Protocol
status: stable
stale_after: "2027-01-01T00:00:00Z"
version: 1.0
description: Autonomous protocol for Antigravity to poll all Jules sessions, unblock stuck or paused agents by approving plans or answering questions, evaluate completed tasks against develop, and write an actionable triage review for Human-in-the-Loop (HITL) approval.
tags: [workflow, jules, hitl, pr-review, triage, mcp]
generated: {by: process:okf-updater, at: "2026-09-28T22:30:00Z"}
verified: {by: process:okf-updater, at: "2026-09-28T22:30:00Z"}
sources:
- id: agent_index
  resource: .agents/index.md
- id: sim_benchmark
  resource: scripts/run_sim_benchmark.py
---

# Jules Session & Task Triage Protocol

Autonomous workflow for Antigravity to audit, unblock, and evaluate all asynchronous Jules sessions and pull requests, generating a comprehensive decision report for the Human-in-the-Loop (HITL).

## Trigger

Execute via slash command `/jules-session-triage` or invoke during periodic triage sweeps to unblock paused tasks and evaluate finished PRs.

## Sequence

### Phase 1: Real-Time Session Discovery & Liveness Audit

* **Query Active Sessions:** Query all active and recent sessions via the Jules MCP or API (`GET /sessions?pageSize=50`).
* **State Categorization:** Group sessions by their lifecycle state:
  * `AWAITING_USER_FEEDBACK`: Tasks paused waiting for human intervention or plan approval.
  * `PAUSED`: Tasks paused due to environmental constraints or quota limits.
  * `IN_PROGRESS`: Tasks currently executing in the cloud sandbox.
  * `COMPLETED`: Finished tasks with PRs or proposed patches.
  * `FAILED`: Errored or aborted sessions.

### Phase 2: Stuck Session Recovery & Interactive Unblocking

For each session in `AWAITING_USER_FEEDBACK` or `PAUSED`:

* **Inspect Activity Log:** Fetch recent events via `jules_get_activities(sessionId)` or `GET /sessions/{id}/activities`.
* **Plan Approval Gate:** If the session generated a plan awaiting user confirmation (`planGenerated`), invoke `jules_approve_plan(sessionId)`.
* **Question & Prompt Response:** If the agent paused requesting feedback or guidance:
  * Determine the blocker (e.g., benchmark regression, ambiguous requirement, or architectural choice).
  * Formulate precise, actionable guidance aligning with PHIDS ECS invariants and performance benchmarks.
  * Send the prompt via `jules_send_message(sessionId, message)` or `POST /sessions/{id}:sendMessage` with payload `{"prompt": "<guidance>"}` (crucial: field name in Google Jules API is `prompt`).
* **Liveness Assertion:** Re-query session state to verify transition to `IN_PROGRESS`.

### Phase 3: Completed PR & ChangeSet Deep Evaluation

For each completed session and its corresponding GitHub Pull Request:

* **Mergeability & Git Conflict Analysis:**
  * Run `gh pr view <id> --json mergeable,mergeStateStatus`.
  * If `mergeable == "CONFLICTING"`, inspect diff against `origin/develop` to determine whether the change was already superseded by local commits.
* **CI Gates & Diff Coverage:**
  * Run `gh pr checks <id>`.
  * If failing, inspect failure logs via `gh run view --log-failed <run-id>`.
  * Verify `diff-cover` threshold (>= 80% coverage on new lines).
* **Benchmarking & Latency Impact:**
  * Evaluate benchmark comparison against baseline `develop` (`just bench-compare-jit`).
  * Verify tick rate impact. Reject any change showing regression on reference scenarios (e.g., `rectangular_crossfire_extended.json`).
* **Architectural & Invariant Soundness:**
  * Verify branchless float masking (Rule 05-B).
  * Verify zero-allocation loop rules (Rule 02).
  * Check Data-Flow Matrix table-to-trace parity (Rule 05-A).

### Phase 4: Standardized HITL Review Report Generation

Generate a structured review artifact for the human reviewer (`HITL_TRIAGE_REPORT.md`) containing:

* **Executive Summary:** Count of active, unblocked, completed, and recommended PRs.
* **Triage Decision Matrix:**
  * 🟢 **RECOMMENDED TO MERGE:** PRs passing all CI checks, zero conflicts, verified speedups or architectural cleanups.
  * 🟡 **REQUIRES REBASE / ADAPTATION:** High-value PRs with minor branch divergence or coverage gaps.
  * 🔴 **RECOMMENDED TO DISCARD / REJECT:** PRs with performance regressions, failing coverage, or superseded logic.
  * 🔄 **ACTIVE / UNBLOCKED SESSIONS:** Running tasks with current status and unblocking prompts sent.
* **One-Click Action Commands:** Provide explicit `gh pr merge` or `gh pr close` commands for each PR.
