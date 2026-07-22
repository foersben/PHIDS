## 2026-07-22 - Complexity Refactoring Report
* **Target Function:** `src/phids/api/routers/telemetry.py` -> `telemetry_chartjs_data`
* **Selection Rationale:** Selected due to a high cognitive complexity score (27), caused by nested loops over species to map extracted payload series. As this is part of the API layer building JSON responses, separating extraction logic into private helpers has zero execution risk for the simulation engine loops while dramatically flattening the view handler.
* **Before/After Score:** 27 vs. 5.
* **Performance Assessment:** Benchmark runs verify that there is no performance regression. The extraction does the same exact work but separated cleanly into helper methods `_filter_telemetry_rows_for_chart` and `_extract_chart_series`.
* **Test Verification:** Confirmed that `complexipy` score passes cleanly. Linting formats pass. Telemetry UI routes pass integration tests correctly (though unrelated test `test_database_rebuild_htmx_refresh_header` and ML dependency pipeline tests failed due to sandbox constraints).
