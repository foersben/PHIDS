---
type: Agent Rule
trigger: always_on
description: Clean code standards, parameter arity limits, docstring formats, and antipattern prohibitions.
---

# Clean Code & Architectural Invariants

Mandates governing code structure, parameter arity, docstring completeness, and event loop safety.

## 1. Parameter Arity & Signature Hygiene

* **Arity Ceiling (NI-06-ARITY):** Non-JIT public functions and methods must have parameter arity $\le 4$ (excluding `self`/`cls`).
* **Parameter Models:** When operations require $> 4$ parameters, encapsulate parameters in `@dataclass(slots=True, frozen=True)` parameter bags or Pydantic schemas.
* **Tuple Returns (Smell A):** Never return naked multi-element positional tuples (`tuple[float, int, bool]`) from public services or presenters. Use `NamedTuple` or frozen dataclasses.

## 2. Docstring Standards

* **Google-Style 4-Part Structure:** Every public module, class, and function must feature:
  1. A concise single-line summary ending in a period.
  2. Architectural context and computational purpose.
  3. Exhaustive `Args:` and `Returns:` with types and physical/biological units where applicable.
  4. `Raises:` documenting thrown exceptions.

## 3. Async Event Loop Safety

* **Zero Blocking I/O in Async Handlers:** Inside `async def` routes (`src/phids/api/routers/`), blocking synchronous filesystem operations, heavy Polars transforms, or synchronous Zarr reads are strictly prohibited.
* **Offloading:** Delegate blocking or CPU-bound tasks to worker threads via `asyncio.to_thread(...)`.

## 4. Protected Engine Hot Paths

* **Critical Path Globs:** `src/phids/engine/core/**/*.py`, `src/phids/engine/systems/**/*.py`.
* **Zero Structural Refactoring Without Invariant Gates:** Any modification to hot-path modules must verify:
  * Parity: `just test-parity`
  * Replay: `just test-replay`
  * Zero Allocation: `uv run pytest --no-cov -m heap_allocation`
