## The Discrepancy

The Zensical documentation in `docs/scenario_guide/scenario_authoring.md` strictly specifies a maximum of "16 Substance Profiles" globally within a scenario as part of the "Rule of 16" bounds. However, the existing `SimulationConfig` Pydantic model (`src/phids/api/schemas/simulation.py`) only enforced that `num_signals <= 16` and `num_toxins <= 16` individually. This allowed configurations to declare 16 signals and 16 toxins, resulting in up to 32 total substance profiles.

## The Action

I added a new root validator (`@model_validator(mode="after")`) to `SimulationConfig` in `src/phids/api/schemas/simulation.py` to enforce that `self.num_signals + self.num_toxins <= MAX_SUBSTANCE_TYPES`. I also added a unit test (`test_simulation_config_enforces_total_substance_limit`) in `tests/unit/api/test_schemas_and_invariants.py` and updated the existing saturated matrix test to use 8 signals and 8 toxins (summing to 16) instead of 16 of each.

## The Justification

This change was absolutely necessary because exceeding the 16 substance profiles limit fundamentally breaks the `Rule of 16` pre-allocation constraints which guarantee determinism and bounded memory usage in the Numba-accelerated fast paths. The simulation's system architecture requires these 16x16 bounds, and if the API ingress permits up to 32 substances, the pre-allocated integer matrices used for flow fields and defense logic will experience out-of-bounds index errors or buffer overflows in the execution environment. Adding this schema constraint perfectly synchronizes the codebase with the structural constraints documented in `scenario_authoring.md`.
