### 🧬 Surviving Mutant Analysis

* **Target File & Function:** `src/phids/engine/core/biotope.py` -> `set_plant_energy`
* **Mutant ID:** `phids.engine.core.biotope.xǁGridEnvironmentǁset_plant_energy__mutmut_6`
* **The Mutation:**
```diff
- self._plant_energy_by_species_write[species_id, x, y] = max(0.0, value)
+ self._plant_energy_by_species_write[species_id, x, y] = max(1.0, value)
```
* **Why it survived:** Existing tests either wrote high energy values (e.g. 10.0, where `max(0.0, 10.0)` == `max(1.0, 10.0)`) or cleared to exactly 0.0, allowing a mutation that clamped the lower bound to 1.0 to survive undetected.
* **The Killer Test:** Added `test_set_plant_energy_fractional_value` in `tests/unit/engine/core/test_biotope_state_mutation_pilot.py` asserting that a fractional input `0.5` sets the value to `0.5` rather than being clamped to `1.0`.
* **Proof of Kill:** Confirmed that `mutmut` now flags this mutant as KILLED and all `pytest` / `mypy` suites pass.
