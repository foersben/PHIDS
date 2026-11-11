1. **Target Selection**:
   The command `find src/phids/ -name "*.py" -exec wc -l {} + | sort -rn | head -n 15` was run. We found `src/phids/engine/systems/interaction/movement/choices.py` with 460 lines, which satisfies the requirement for a >400-line monolithic module. This file can be extracted cleanly into `jit.py` and `python.py` as pure free functions without touching the internals of the `@njit` kernels themselves, thus adhering to memory rules.

2. **Refactoring `src/phids/engine/systems/interaction/movement/choices.py`**:
   Create the directory `src/phids/engine/systems/interaction/movement/choices/`.
   Extract the file into the following modules using `run_in_bash_session` to run exact `sed` extractions and write the `__init__.py` file:
   - `jit.py`: Extract imports and the `_jit` suffixed functions from `choices.py`.
   - `python.py`: Extract imports and the Python fallback functions from `choices.py`.
   - `__init__.py`: Re-export all functions to maintain a seamless interface.

3. **Verify File Structure**:
   Use `ls -R src/phids/engine/systems/interaction/movement/choices/` to verify the creation of the package and its sub-modules.

4. **Verify Application Logic and Constraints**:
   Run the following validation commands to ensure quality and invariant boundaries are met:
   ```bash
   uv run ruff format .
   uv run ruff check .
   uv run mypy src/phids
   uv run pytest
   uv run python scripts/audit_matrix_coverage.py
   uv run python scripts/verify_matrix_trace_parity.py --all
   uv run python scripts/validate_okf.py
   ```

5. **Journaling to Memory**:
   Log learning to `.agents/memory/chisel.md` dynamically using an unquoted heredoc `cat << EOF >>`.

6. **Pre-commit Steps**:
   Complete pre-commit steps to ensure proper testing, verification, review, and reflection are done.

7. **Submit PR**:
   Call the `submit` tool with proper PR description.
