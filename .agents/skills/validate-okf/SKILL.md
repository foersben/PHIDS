---
type: Agent Skill
title: Trigger
status: active
version: 0.1
description: Skill to verify that markdown files contain correct frontmatter.
tags: [python]
generated: {by: process:okf-updater, at: "2026-07-21T16:01:38Z"}
name: Validate Open Knowledge Format
sources:
- resource: scripts/validate_okf.py
---

# Trigger

When creating or heavily modifying files in `docs/` or `.agents/`.

# Execution

```bash
uv run python scripts/validate_okf.py
```
