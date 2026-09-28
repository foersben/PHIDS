---
type: Reference
title: PHIDS Docs Domain Guidelines
status: stable
stale_after: "2027-06-01T00:00:00Z"
version: 1.0
description: Quick-reference documentation and markdown formatting constraints for the docs domain.
tags: [docs, okf, guidelines]
generated: {by: process:agent-config-refactor, at: "2026-09-28T00:00:00Z"}
sources:
  - id: rule_04
    resource: .agents/rules/04-markdown-formatting.md
---

# PHIDS Docs Domain - Quick-Reference Constraints

Full constraints in `.agents/rules/04-markdown-formatting.md`.

## Critical Summary

* ALL docs/ files require exhaustive OKF frontmatter:
  `type`, `title`, `status`, `version`, `description`, `tags`, `generated`, `sources`.
* Hyphens: ASCII `-` only. Never en-dash or em-dash.
* Lists: `*` with 1 space after, 2-space indent per level.
* 1 blank line before/after all lists, code blocks, headings.
* Zero truncation of existing prose. Never compress narrative into bullets.
* Validate before commit: `uv run python scripts/validate_okf.py`

Role: `05-docs-librarian`.
