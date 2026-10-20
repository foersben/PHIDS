### 🧬 Surviving Mutant Analysis

* **Target File & Function:** `src/phids/engine/core/ecs.py` -> `remove_component`
* **Mutant ID:** `phids.engine.core.ecs.xǁEntityǁremove_component__mutmut_3`
* **The Mutation:**
```diff
- self._components.pop(component_type, None)
+ self._components.pop(component_type, )
```
* **Why it survived:** The existing tests in `test_ecs_mutation_pilot.py` only covered the "happy path" where a component is successfully removed. Because there were no tests attempting to remove a component that the entity did not possess, the mutated code (which would raise a `KeyError` instead of gracefully returning `None`) was never exercised in a failing state.
* **The Killer Test:** Added `test_ecs_entity_remove_nonexistent_component` in `tests/unit/engine/core/test_ecs_mutation_pilot.py` asserting that calling `remove_component` with an unattached component type fails gracefully without raising a `KeyError`.
* **Proof of Kill:** Confirmed that `mutmut` now flags this mutant as KILLED and all `pytest` / `mypy` suites pass.
