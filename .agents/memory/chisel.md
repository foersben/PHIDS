## 2026-07-07 - Refactoring telemetry.export

Learning: When splitting a monolithic file (like `telemetry/export.py`), `pytest` may fail with `AttributeError` or `ImportError` if integration tests still rely on an aliased import like `from phids.telemetry import export as telemetry_export` without updating all nested function calls.
Action: Next time, when refactoring a file, proactively grep for all aliased imports of that module in the tests directory to ensure they are updated to match the new package structure.
