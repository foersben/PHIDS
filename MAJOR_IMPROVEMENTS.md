# Clean Code Improvements

## Safe imports (Applied)
We consolidated several function-level imports to the module level scope:
- `import polars as pl` in `api/main.py`.
- `import uuid` and `import datetime` in `api/routers/batch.py`.
- `import shutil` in `io/zarr_replay.py`.

## Deferred Major Improvements
1. **Break `engine` -> `api.schemas` circularity:**
   Several `engine/` modules (like `engine/systems/lifecycle.py` and `engine/batch.py`) perform local imports of objects from `phids.api.schemas` (such as `FloraSpeciesParams`, `SimulationConfig`, etc.). Moving these out into global scope introduces complex circular dependencies during module loading.
   A better clean code solution that requires a major architectural change would be to extract the shared domain configuration schemas into a separate module (e.g. `phids.core.schemas` or `phids.domain.config`) so that both `api/` and `engine/` can import them without risking circular dependencies.

2. **Lazy Optional Dependencies:**
   Currently, modules like `telemetry/export.py` rely on local inline imports for `pandas` and `matplotlib` to support headless optional-dependency execution without crashing the runtime for users omitting them. Though it looks untidy, moving them to the global scope actively breaks functionality if these environments are un-bundled.
   A future architectural fix could be to segregate `export.py` into multiple distinct strategy classes or separate backend modules (`export_polars.py`, `export_pandas.py`), allowing safer conditional importing at the top level per module rather than burying inline imports inside functions.
