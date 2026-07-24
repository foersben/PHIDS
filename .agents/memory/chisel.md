---
type: memory
name: chisel
description: Refactoring dashboard presenter monolithic logs and learnings
---


## 2026-07-10 - Refactoring Dashboard Presenter Monolith
Learning: When extracting logic from a large presenter monolith (`dashboard.py`) into smaller cohesive modules (`helpers.py`, `cell_details.py`, `payloads.py`, `mycorrhizal.py`, `substances.py`), it is critical to ensure a 1:1 structural translation. If any payload dictionary keys are modified, missing, or renamed (e.g. `species_energy` vs `plant_energy`), or if state evaluation logic is inadvertently inverted (`active` vs `not active`), frontend and API tests will break. Refactoring must strictly maintain backwards compatibility with existing consumers.

Action: Run all tests after each structural extraction to ensure invariant behavior and schemas are fully preserved before moving to the next chunk of code.
## 2026-07-13 - Extracting shared pure functions
Learning: When extracting pure utility functions out of multiple domain modules into a single shared utility file (e.g. `shared.py` from `helpers.py`, `mycorrhizal.py`), you need to be very careful that the implementation extracted matches the tests that depend on it. In this case, `_describe_activation_condition` in `helpers.py` had small string formatting differences (`count ≥` vs `≥`, `is active` vs `active`, `concentration >` vs `concentration ≥`, `empty all_of` vs `unconditional`) from the tests, causing test failures. Always ensure the extracted implementation strictly matches the integration tests expectation.
Action: Run integration tests frequently and trace the specific formatting discrepancies before relying on simple file merges.
