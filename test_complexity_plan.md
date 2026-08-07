1. **Target Selection**:
   - I have selected `_apply_toxin_to_swarms` in `src/phids/engine/systems/signaling/emission.py`.
   - **Rationale**: It has a complexity of 15. The logic is a very straightforward iteration over swarms, applying lethality and repellency, then GCing. Extracting the per-swarm lethality logic (which has nested `if` statements) into a helper function `_apply_toxin_lethality` will reduce the cognitive complexity of the main loop without adding overhead, as this is standard Python loop extraction (in a non-jit hotpath). It provides a clean untangling with very low performance risk.

2. **Refactoring Step**:
   - Extract the lethality application block from `_apply_toxin_to_swarms` into a new helper function `_apply_lethal_toxin_effect(swarm, toxin_val, lethality_rate)`.
   - Update `_apply_toxin_to_swarms` to call this helper.

3. **Complete pre-commit steps to ensure proper testing, verification, review, and reflection are done.**
   - Run `uv run ruff format .` and `uv run ruff check . --fix`
   - Run `uv run pytest`
   - Run `uvx complexipy src/phids/engine/systems/signaling/emission.py --plain` to verify score resolution
   - Append to `.agents/memory/complexity.md`

4. **Submit**:
   - Submit the branch `refactor-complexity-toxin`.
