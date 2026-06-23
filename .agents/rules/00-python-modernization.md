---
type: rule
trigger: always_on
rule_id: python-modernization
severity: critical
---
# Mandates
- **Execution:** Ban `pip`, `poetry`, `python`. Execute ALL commands via `uv run` or `just`.
- **Types:** Enforce strict `mypy`. Type all function signatures, generics, and variable assignments explicitly.
- **Linting:** Validate all code via `uv run ruff check` and `uv run ruff format`. Ban `flake8`, `black`, `isort`.