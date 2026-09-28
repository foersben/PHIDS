# PHIDS Master Agent Router

<!-- UNIVERSAL RULES: apply to all AI agents (Antigravity, Jules, Copilot, etc.) -->

All Python commands MUST use `uv run`. Never bare `python`, `pip`, `uvx`, or `poetry`.
All commits must be GPG/SSH signed. Stop and escalate if signing fails.
Pre-commit gates (run before ANY commit to `engine/` or `api/schemas/`):

```bash
uv run python scripts/audit_matrix_coverage.py
uv run python scripts/verify_matrix_trace_parity.py --all
uv run ruff check src/ && uv run mypy src/
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
3. **Restricted directories.** Do NOT open `.agents/memory/` or `.agents/manifesto/`
   unless the user prompt uses the words `historical`, `manifesto`, or `canon`.
4. **Do NOT crawl `.agents/` blindly** or pre-load all role files.
