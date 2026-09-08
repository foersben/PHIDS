## Canon Justification Report: Aligning Pydantic Schemas with Biological Documentation

**1. PlantComponentSchema Field Discrepancies**

*   **The Discrepancy:** The `PlantComponentSchema` defined in `src/phids/api/schemas/ecs.py` was missing fields recently added as part of the Dual-Proxy Architecture and mycorrhizal networking (Plan 2 implementation). The missing fields were: `seed_drop_height`, `seed_terminal_velocity`, `last_energy_loss_cause`, `mycorrhizal_connections`, `mycorrhizal_tax_per_link`, `target_nutrition_factor`, `translocation_rate`, `structural_mass`, `max_structural_mass`, and `growth_rate_structural`.
*   **The Action:** Added the missing fields with exact type annotations, defaults, and bounds directly extracted from `src/phids/engine/components/plant.py` and the `flora_and_symbiosis.md` documentation.
*   **The Justification:** The documentation clearly dictates that `PlantComponentSchema` must accurately reflect the `PlantComponent` runtime state for valid REST and WebSocket telemetry inspection. Leaving the schemas mismatched allows hidden simulation state that operators cannot inspect, violating the contract that all biological reality must be serializable and verifiable. Specifically, missing dual-proxy tracking (`structural_mass`) breaks observability of morphological resistance, and missing `apparent_nutrition_factor` details (`translocation_rate`, `target_nutrition_factor`) hides the phloem response mechanism documented extensively in section 2.3 of `flora_and_symbiosis.md`.

**2. ResourceWithdrawalAction Constraint Misalignment**

*   **The Discrepancy:** In `src/phids/api/schemas/triggers.py`, the `ResourceWithdrawalAction` bounded `withdrawal_duration` using `gt=0`. However, the documentation for withdrawal ticks and related implementation components strictly specify this constraint as `ge=1` (since it represents discrete ticks remaining).
*   **The Action:** Modified `src/phids/api/schemas/triggers.py` replacing `gt=0` with `ge=1` on the `withdrawal_duration` field.
*   **The Justification:** While mathematically equivalent for integers, Canonical alignment requires absolute parity with documented constraints. Allowing `gt=0` introduces documentation drift and sets a precedent for loose bounds interpretation. Enforcing `ge=1` explicitly affirms that fractional ticks are invalid and the minimum atomic time step is exactly 1 discrete loop interval.
