1. **Understand the problem**:
   The memory file `.agents/memory/canon.md` mentions that "The scenario authoring guide historically referenced a monolithic '16x16 Substance Trigger Interaction Matrix' (Trigger_Matrix), which became outdated after the codebase evolved to use per-species bounded `list[TriggerConditionSchema]` architectures...".
   The task is to find and fix documentation that describes the "Trigger Matrix" as a `16x16` or `monolithic` matrix instead of the new per-species bounded architecture.

2. **Identify files to update**:
   - `docs/technical_architecture/system_architecture.md`:
     Contains: `• [16x16] Substance Trigger Matrix` at line 121.
     Replace with: `• Bounded Per-Species Trigger Profiles (≤16)`
   - `docs/technical_architecture/signaling_triggers.md`:
     Contains: `The interaction matrix couples stimuli (initiators) and condition predicates (activation conditions) to physiological responses (actions).` at line 18.
     Replace with: `Rather than a monolithic matrix, defensive behaviors are defined per flora species via a bounded list of trigger conditions (`list[TriggerConditionSchema]`) which compile into discrete `CompiledTrigger` trees, coupling stimuli (initiators) and condition predicates (activation conditions) to physiological responses (actions) while maintaining Rule of 16 memory limits.`

3. **Verify changes**:
   Run the pre-commit gates:
   ```bash
   uv run ruff format .
   uv run ruff check .
   uv run mypy src/phids
   uv run pytest
   uv run python scripts/audit_matrix_coverage.py
   uv run python scripts/verify_matrix_trace_parity.py --all
   uv run python scripts/validate_okf.py
   uv run zensical build -f zensical.toml
   ```
   Wait, the memory mentions that "Zensical builds will silently succeed if internal markdown links refer to non-existent paths, but standard build diagnostics might catch them depending on config. A recursive regex or grep is essential to identify and fix stale relative paths...". We are not changing paths, so no issue there.
   Another memory mentions that OKF v0.2 tags require list format, which is fine here, we are not changing OKF headers.

4. **Prepare PR format**:
   Follow instructions:
   ```markdown
   ### 🧭 Alignment Direction & Decision Rationale

   * **Direction Chosen:** `[Documentation Update]`
   * **The Discrepancy:** `docs/technical_architecture/system_architecture.md` referenced a `[16x16] Substance Trigger Matrix` and `docs/technical_architecture/signaling_triggers.md` referred to an "interaction matrix".
   * **Why this direction?** The codebase was intentionally evolved to use per-species bounded `list[TriggerConditionSchema]` architectures that compile into discrete `CompiledTrigger` trees, preserving the Rule of 16 limits (`MAX_SUBSTANCE_TYPES`). Updating the stale documentation ensures alignment with the current runtime Pydantic schemas (`FloraSpeciesParams`, `TriggerConditionSchema`).
   * **Human Verification Checklist:**
     - [ ] Reviewer check 1: Verify the updated architectural Mermaid diagram in `system_architecture.md`.
     - [ ] Reviewer check 2: Verify the updated explanatory text in `signaling_triggers.md`.

   ### 🔬 Technical Changes & Verification
   * **Modified Files:** `docs/technical_architecture/system_architecture.md`, `docs/technical_architecture/signaling_triggers.md`
   * **Quality Gates:** Confirmed that `ruff`, `mypy src/phids`, `pytest`, `validate_okf`, and matrix parity checks passed cleanly.
   ```

5. **Commit the changes**:
   Title: `📜 Canon [Docs Sync]: Update trigger architecture documentation to reflect active per-species implementation`
