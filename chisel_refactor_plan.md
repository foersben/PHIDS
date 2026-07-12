1. Extract helper functions `_coerce_int`, `_coerce_float`, `_default_substance_name`, `_describe_activation_condition`, and `validate_cell_coordinates` into a new `shared.py` module in `src/phids/api/presenters/dashboard/`.
2. Move the substance-related utility functions (`_is_live_substance_visible`, `_live_substance_state_payload`, `_serialize_live_substance`, `_fallback_live_substance_payload`) that are currently duplicated into `src/phids/api/presenters/dashboard/substances.py`.
3. Move the mycorrhizal-related utility functions (`build_draft_mycorrhizal_links`, `_build_live_mycorrhizal_links`, `_links_touching_cell`) that are currently duplicated into `src/phids/api/presenters/dashboard/mycorrhizal.py`.
4. Delete the duplicated monolithic functions in `mycorrhizal.py` and `substances.py`, retaining only their core domain functions.
5. Update all imports across the repository (`__init__.py`, `cell_details.py`, `payloads.py`, `routers/ui.py`, `api/main.py` etc.) to point to the new, modular structure.
6. Run `uv run ruff check .`, `uv run ruff format .`, and `uv run pytest`.
7. Add a pre-commit step check.
8. Submit a PR outlining the architectural un-tangling of `helpers.py`.
