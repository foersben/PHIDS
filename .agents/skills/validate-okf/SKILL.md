---
type: skill
title: Trigger
status: active
version: 0.1
description: Skill to verify that markdown files contain correct frontmatter.
tags:
- python
timestamp: "2026-07-21T16:01:38Z"
resources:
- scripts/validate_okf.py
name: Validate Open Knowledge Format
---

# Trigger

When creating or heavily modifying files in `docs/` or `.agents/`.

# Execution

```bash
uv run python scripts/validate_okf.py
```
