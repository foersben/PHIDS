# PHIDS Master Agent Router

<!-- UNIVERSAL RULES: apply to all AI agents (Antigravity, Jules, Copilot, etc.) -->

* All Python commands MUST use `uv run` or `just`. Never bare `python`, `pip`, `uvx`, or `poetry`.
* Never run `act` in agent sandboxes; `act` is for local workstation Docker runs only.
* Commit signing:
  * **Local agents (Antigravity) & human developers:** Commits MUST be GPG/SSH signed (`git commit -S`). Stop and escalate if signing fails.
  * **Cloud sandbox agents (Jules):** Creates PR feature branches without `-S`. Commits are signed upon PR merge via GitHub Web-Flow.
* Pre-commit gates (run before ANY commit to `engine/` or `api/schemas/`):

```bash
uv run python scripts/audit_matrix_coverage.py
uv run python scripts/verify_matrix_trace_parity.py --all
uv run ruff check src/ && uv run mypy src/phids
```

<!-- JULES-SPECIFIC: session routing and token guardrail instructions.
     Antigravity IDE: these sections are Jules session-management metadata.
     They do not override or contradict .agents/AGENTS.md. -->

## Jules: Mandatory First Step

Open `.agents/index.md` and follow its decision matrix before touching any file.
Stop loading additional files once you have a role assignment.

## Jules: Hard Routing Rules

1. **Route first.** Read `.agents/index.md` decision matrix before any action.
2. **Path-scoped roles.** Load only the role file for the paths you are modifying.
   Domain-specific rules auto-load from sub-directory AGENTS.md files:
   `src/phids/engine/AGENTS.md`, `src/phids/api/AGENTS.md`, `docs/AGENTS.md`.
3. **Commit protocol.** Push PR feature branch directly without `git commit -S`.
4. **Restricted directories.** Do NOT open `.agents/memory/` or `.agents/manifesto/`
   unless the user prompt uses the words `historical`, `manifesto`, or `canon`.
5. **Do NOT crawl `.agents/` blindly** or pre-load all role files.

## Agent Resources & Capability Manifest

* **Skills Directory:** Programmatic verification skills reside in `.agents/skills/` (`validate-okf`, `run-benchmarks`, `audit-okf-matrix-coverage`, `verify-matrix-trace-parity`, `auto-reconcile-matrix-drift`, `analyze-zarr`, `visualize-okf`).
* **Jules Prompt Templates:** Standardized canned prompts for autonomous background personas (`Chisel`, `Bolt`, `Canon`, `Complexity`, `Sentinel`, `Vigil`) are defined in `.agents/PROMPT_TEMPLATE.md`.
* **Task Offloading:** Antigravity agents should evaluate whether broad or token-intensive tasks (complexity refactors, multi-scenario JIT benchmarks, mutation testing) should be offloaded to cloud Jules agents to conserve workstation context tokens.
