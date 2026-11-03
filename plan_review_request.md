I have identified a surviving mutant in `src/phids/engine/core/biotope.py` in the `set_plant_energy` method.
Mutant ID: `phids.engine.core.biotope.xǁGridEnvironmentǁset_plant_energy__mutmut_6`
Original code: `self._plant_energy_by_species_write[species_id, x, y] = max(0.0, value)`
Mutated code: `self._plant_energy_by_species_write[species_id, x, y] = max(1.0, value)`

To kill this mutant, I need to add a killer test in `tests/unit/engine/core/test_biotope_state_mutation_pilot.py` where we call `set_plant_energy` with a `value` between 0.0 and 1.0 (e.g., 0.5) and assert that the value is properly set to 0.5. Currently, existing tests either use 10.0 or 0.0 (or they test clamping but not for small positive values).

The test will look like this:
```python
def test_set_plant_energy_fractional_value() -> None:
    """Validate that fractional plant energy > 0.0 but < 1.0 is not incorrectly clamped to 1.0."""
    env = GridEnvironment(width=5, height=5, num_signals=1, num_toxins=1)

    # Write a fractional energy value < 1.0
    env.set_plant_energy(1, 1, 0, 0.5)

    # Assert that it correctly stores 0.5, rather than clamping to 1.0
    assert env._plant_energy_by_species_write[0, 1, 1] == 0.5
```

This perfectly targets the untested gap in condition checking.

### Execution Plan:
1.  **Add Killer Test:** Append the above test to `tests/unit/engine/core/test_biotope_state_mutation_pilot.py`.
2.  **Verify Test Suite:** Run `uv run pytest tests/unit/engine/core/test_biotope_state_mutation_pilot.py` to ensure it passes.
3.  **Complete pre-commit steps to ensure proper testing, verification, review, and reflection are done:** Run `uv run ruff format .`, `uv run ruff check .`, `uv run mypy src/phids`, `uv run pytest`, `uv run python scripts/audit_matrix_coverage.py`, and `uv run python scripts/verify_matrix_trace_parity.py --all`.
4.  **Submit PR:** Use the `submit` tool to finalize the change with the Vigil persona format.
