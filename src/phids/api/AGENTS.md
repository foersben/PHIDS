# PHIDS API Domain - Quick-Reference Constraints

Full role constraints in `.agents/roles/07-api-and-ui-developer.md` (routers)
or `.agents/roles/02-scientific-architect.md` (schemas/services).

## Critical Summary

* Rule of 16: `num_signals + num_toxins <= MAX_SUBSTANCE_TYPES` (16).
  Validate with `model_validator(mode="after")` in Pydantic schemas.
* Component schemas must maintain 1:1 field parity with ECS array counterparts.
* HTMX UI -> `DraftService` -> `DraftState` only. Never mutate live loop directly.
* `POST /api/scenario/load-draft` is the only commit path to the live loop.
* Use `APIRouter()` + `include_router()` for splits. No backwards-compat shims.

## Pre-Commit Gate (schemas + services only)

```bash
uv run python scripts/audit_matrix_coverage.py
uv run python scripts/verify_matrix_trace_parity.py --all
uv run ruff check src/ && uv run mypy src/
```
