## Objective
Refactor `export_telemetry_format` in `src/phids/api/routers/telemetry.py` to reduce its cognitive complexity below 15 without introducing performance overhead.

The function currently has a complexity of 15 because it has multiple if-else branches for the different formats (`csv`, `tex_table`, `tex_tikz`, `png`) and each branch has a nested local function `_build_export_X()` defined and then run in threadpool.

## Plan

1. **Extract private helper functions for formats:** Move the `_build_export_X()` logic into private module-level async functions or just private synchronous functions that are invoked via `run_in_threadpool`.
2. **Flatten the logic:** Replace the long `if format == ...` chain with a simple mapping or just keep the if-else but since the inner functions are no longer defined inside, the cognitive complexity of `export_telemetry_format` will drop significantly.
3. **Verify:** Run tests and check the new complexity score using `complexipy`.
4. **Complete Pre-Commit Steps:** Complete pre-commit steps to ensure proper testing, verification, review, and reflection are done.
5. **Submit:** Provide final results.
