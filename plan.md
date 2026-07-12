1. **Target**: `src/phids/api/presenters/dashboard/helpers.py` is a 1089-line monolithic "god class" file that contains mixed responsibilities including scalar coercion, UI state payload generation, cell details payload construction, and full dashboard dashboard construction.
2. **Action**: Break down `helpers.py` into distinct, cohesive modules:
   - `shared.py`: Common pure-utility functions (`_coerce_int`, `_coerce_float`, `validate_cell_coordinates`, `_default_substance_name`, `_describe_activation_condition`).
   - `mycorrhizal.py`: Extract mycorrhizal networking specific functions (`build_draft_mycorrhizal_links`, `_build_live_mycorrhizal_links`, `_links_touching_cell`).
   - `substances.py`: Extract substance specific functions (`_is_live_substance_visible`, `_live_substance_state_payload`, `_serialize_live_substance`, `_fallback_live_substance_payload`).
   - `cell_details.py`: Extract cell specifics tooltip generator functions (`build_live_cell_details`, `build_preview_cell_details`).
   - `payloads.py`: Extract top level payload generator (`build_live_dashboard_payload`).
3. **Clean Up**: Remove `helpers.py`. The files `mycorrhizal.py`, `substances.py`, `cell_details.py`, `payloads.py` ALREADY exist in `src/phids/api/presenters/dashboard/` and contain duplicated code or stubs. I will ensure they are fully populated and correct. I will also create `shared.py` for the core utilities.
4. **Update Imports**: Update all intra-package imports in `src/phids/api/presenters/dashboard/__init__.py` and other modules to import from `shared.py` (or directly from the newly updated files) instead of `helpers.py`. Update references in `src/phids/api/main.py`, `src/phids/api/routers/ui.py`, etc.
5. **Testing**: Run `uv run ruff check .`, `uv run ruff format .`, and `uv run pytest` to guarantee no broken imports and deterministic logic is retained.
6. **Pre-commit**: Complete pre-commit steps to make sure proper testing, verifications, reviews and reflections are done.
7. **Submit**: Create PR to present structural upgrade.
