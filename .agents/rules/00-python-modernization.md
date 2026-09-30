---
type: Agent Rule
title: Mandates
status: stable
stale_after: "2027-01-01T00:00:00Z"
version: 0.1
description: "- **Execution:** Ban `pip`, `poetry`, `python`. Execute ALL commands
  via `uv run` or `just`."
tags: [python]
generated: {by: process:okf-updater, at: "2026-07-21T16:01:38Z"}
verified: {by: process:okf-updater, at: "2026-08-14T16:00:00Z"}
trigger: always_on
rule_id: python-modernization
severity: critical
---

# Mandates

- **Execution:** Ban `pip`, `poetry`, `python`. Execute ALL commands via `uv run` or `just`.
- **Types:** Enforce strict `mypy`. Type all function signatures, generics, and variable assignments explicitly.
- **Linting:** Validate all code via `uv run ruff check` and `uv run ruff format`. Ban `flake8`, `black`, `isort`.
- **FastAPI Router Extraction:** When extracting monolithic FastAPI routers into smaller packages, always define a new `APIRouter()` in the `__init__.py` composition root and use `.include_router()` to recombine them, ensuring backwards compatibility for downstream clients.
