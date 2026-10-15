### 🧭 Alignment Direction & Decision Rationale

* **Direction Chosen:** `[Documentation Update]`
* **The Discrepancy:** The `docs/technical_architecture/system_architecture.md` diagram historically referenced `[16x16] Substance Trigger Matrix`. This became outdated when the engine codebase was upgraded to use per-species bounded `list[TriggerConditionSchema]` architectures compiling into `CompiledTrigger` trees.
* **Why this direction?** Updating the documentation is correct here, as the codebase has intentionally moved towards discrete schemas (`TriggerConditionSchema` up to `MAX_SUBSTANCE_TYPES`) as documented in `.agents/memory/canon.md` (2026-09-30). This PR reflects that active schema change in the architecture documentation to resolve the drift, mirroring a similar fix in `scenario_authoring.md`.
* **Human Verification Checklist:**
  - [ ] Reviewer check 1: Confirm that the modified mermaid diagram in `docs/technical_architecture/system_architecture.md` renders properly in Markdown viewers and no longer says "[16x16] Substance Trigger Matrix".
  - [ ] Reviewer check 2: Validate the updated Canon memory append in `.agents/memory/canon.md`.

### 🔬 Technical Changes & Verification
* **Modified Files:**
  - `docs/technical_architecture/system_architecture.md`
  - `.agents/memory/canon.md`
* **Quality Gates:** Confirmed that `ruff`, `mypy src/phids`, `pytest`, `validate_okf`, and matrix parity checks passed cleanly.
