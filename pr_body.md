### 🧭 Alignment Direction & Decision Rationale

* **Direction Chosen:** `[Documentation Update]`
* **The Discrepancy:** The `docs/scenario_guide/index.md` and `docs/technical_architecture/system_architecture.md` files referred to a monolithic `[16x16] Substance Trigger Matrix`. However, the current active codebase (`src/phids/api/schemas/species.py` and `triggers.py`) uses a per-species bounded `list[TriggerConditionSchema]` instead, maintaining the Rule of 16 memory limits via `MAX_SUBSTANCE_TYPES`.
* **Why this direction?** The code was intentionally optimized to use per-species schemas, enabling more flexible and accurate trigger condition evaluation via discrete `CompiledTrigger` trees, as noted in the scenario authoring guide itself and in `.agents/memory/canon.md`. Updating the stale documentation correctly aligns the architecture diagrams and summaries with the current runtime state, preserving zero prose truncation.
* **Human Verification Checklist:**
  - [ ] Reviewer check 1: Verify the updated Mermaid diagram in `docs/technical_architecture/system_architecture.md` appropriately replaces the 16x16 Substance Trigger Matrix box with "Per-Species Trigger Condition Bounding".
  - [ ] Reviewer check 2: Verify `docs/scenario_guide/index.md` appropriately references per-species Trigger Conditions instead of a Substance Trigger Matrix.

### 🔬 Technical Changes & Verification
* **Modified Files:** `docs/scenario_guide/index.md`, `docs/technical_architecture/system_architecture.md`
* **Quality Gates:** Confirmed that `ruff`, `mypy src/phids`, `pytest`, `validate_okf`, and matrix parity checks passed cleanly.
