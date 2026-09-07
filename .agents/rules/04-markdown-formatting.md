---
type: Agent Rule
title: Markdown Formatting Rules
status: stable
stale_after: "2027-01-01T00:00:00Z"
version: 1.0
description: Rules for formatting markdown files across the workspace.
tags: [documentation]
generated: {by: process:okf-updater, at: "2026-07-21T16:01:38Z"}
verified: {by: process:okf-updater, at: "2026-09-06T23:00:00Z"}
trigger: always_on
rule_id: markdown-formatting
severity: normal
---

# Markdown Formatting Rules

These rules apply globally across the workspace for editing any markdown file:

* Always use the standard hyphen (`-`) instead of the en-dash or em-dash in all Markdown documentation and UI text.
* Use `*` for all unordered lists.
* List syntax: Exactly 1 space after `*`, indented 2 spaces per level (0 spaces at level 0).
* Insert exactly 1 blank line before/after lists, code blocks, and headings.
* Trim all trailing whitespaces at line ends.
