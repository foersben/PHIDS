---
type: rule
title: Mandates
status: active
version: '0.1'
description: '- **Execution:** Ban `pip`, `poetry`, `python`. Execute ALL commands
  via `uv run` or `just`.'
tags:
- python
timestamp: '2026-07-21T16:01:38Z'
resources: []
trigger: always_on
rule_id: python-modernization
severity: critical
---

# Mandates

- **Execution:** Ban `pip`, `poetry`, `python`. Execute ALL commands via `uv run` or `just`.
- **Types:** Enforce strict `mypy`. Type all function signatures, generics, and variable assignments explicitly.
- **Linting:** Validate all code via `uv run ruff check` and `uv run ruff format`. Ban `flake8`, `black`, `isort`.
