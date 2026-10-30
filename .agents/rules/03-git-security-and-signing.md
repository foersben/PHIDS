---
type: Agent Rule
title: "Rule 03: Git Security & Commit Signing Invariants"
status: stable
stale_after: "2027-01-01T00:00:00Z"
version: 1.0
trigger: always_on
description: Mandatory cryptographic commit signing and git security invariants.
tags: [git, security, gpg, ssh, signing]
generated: {by: "process:agent-os-refactor", at: "2026-10-30T00:00:00Z"}
verified: {by: "process:agent-os-refactor", at: "2026-10-30T00:00:00Z"}
---

# Git Security & Commit Signing Invariants

Mandates governing repository security, commit signing integrity, and key escalation protocols.

## Core Mandates

* **Cryptographic Signing (GPG/SSH):** All commits by local agents (Antigravity) and human developers MUST be signed (`git commit -S`). Unsigned commits or unsigned merges onto local branches are strictly prohibited.
* **Hard Stop on Signing Failure:** If `git commit -S` fails (e.g. `gpg: signing failed: No secret key`, expired key, or locked agent), agents must stop immediately. Do NOT attempt workarounds.
* **Prohibition of Bypass:** Agents are strictly forbidden from modifying `.git/config`, `user.name`, `user.email`, `commit.gpgsign`, or using `--no-gpg-sign`.
* **Escalation Protocol:** When signing fails, present an immediate human escalation checklist per `/delegation-protocol`:
  1. Check keys: `gpg --list-secret-keys` or `ssh-add -l`.
  2. Unlock key: Prompt passphrase via `echo "test" | gpg --clearsign` or `ssh-add ~/.ssh/id_ed25519`.
  3. Resume execution.
* **Cloud Sandbox Agent (Jules) Exception:** Jules creates PR feature branches without `-S`. Cloud commits are cryptographically signed upon merge via GitHub Web-Flow.
