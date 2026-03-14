# Documentation Standards

PHIDS documentation is now a canonical scientific MkDocs corpus rather than a loose collection of
notes. This chapter defines the current documentation standards contributors should follow when they
add or revise prose, docstrings, navigation, or reference material.

## Purpose of the Documentation Layer

The documentation layer in PHIDS has three simultaneous responsibilities:

1. explain the simulator as a scientific and architectural system,
2. trace concepts back to real symbols and modules,
3. preserve migration continuity from the historical markdown corpus.

Good documentation must satisfy all three.

## Canonical Tone and Style

Current canonical documentation should be:

- formal,
- precise,
- current-state oriented,
- explicit about methodological limits,
- traceable to code and tests.

It should avoid:

- aspirational claims presented as implemented facts,
- vague architecture language detached from real modules,
- duplicating large amounts of legacy prose without attribution,
- mixing speculative roadmap ideas into current-state chapters without clear labeling.

## Narrative Docs vs Reference Docs

PHIDS distinguishes two major documentation modes.

### Narrative pages

Narrative pages explain:

- why a subsystem exists,
- how it behaves conceptually,
- what invariants or constraints define it,
- how it fits into the broader project.

Examples:

- `docs/architecture/index.md`
- `docs/engine/*.md`
- `docs/scenarios/*.md`
- `docs/telemetry/*.md`

### Reference pages

Reference pages explain:

- what modules and symbols exist,
- how they are declared,
- what their docstrings say.

Examples:

- `docs/reference/module-map.md`
- `docs/reference/api.md`

Contributors should choose the right mode instead of forcing one page to do both jobs.

## Current-State Rule

Canonical pages should document what the repository currently does.

That means:

- describe actual tick ordering from `SimulationLoop.step()`,
- describe the current `GridEnvironment` buffering model precisely,
- describe the actual `DraftState` to `SimulationConfig` workflow,
- describe current toxin/signal behavior as implemented, even when a richer design discussion exists
  elsewhere.

When the implementation is nuanced or imperfect, the correct documentation strategy is precision, not
silence.

## Symbol and Module Linking

Good PHIDS documentation should link statements to real code anchors whenever practical.

Recommended pattern:

- name the module, symbol, or route explicitly,
- connect prose chapters to the relevant subsystem page,
- keep the module map and API reference synchronized with new public surfaces.

Examples of strong linkage:

- `SimulationLoop`
- `DraftState`
- `ECSWorld`
- `GridEnvironment`
- `ReplayBuffer`
- `TelemetryRecorder`

## Test-Corroborated Claims

When a behavior is verified by tests, contributors should cite the relevant test files or clearly
base the prose on tested current behavior.

This is especially important for:

- lifecycle and interaction edge cases,
- signaling and trigger semantics,
- replay framing,
- UI draft/live behavior,
- curated example-pack guarantees.

## Legacy Provenance Rule

The legacy archive remains important, but it is no longer the canonical active documentation.

When migrating legacy material:

- preserve the archived source in `docs/legacy/`,
- write current canonical pages in fresh prose,
- cite the legacy page as provenance when relevant,
- prefer implementation and tests over legacy design intent when they differ.

This keeps the docs historically grounded without allowing older design memos to override present
runtime truth.

## Docstring Standards

Public-facing Python modules and symbols participate in the documentation surface through
mkdocstrings.

Current docstring expectations include:

- Google-style docstrings,
- triple-quoted strings,
- concise summaries followed by details when needed,
- useful `Args`, `Returns`, `Raises`, `Notes`, or `Examples` sections where appropriate,
- alignment with actual current behavior.

The active enforcement sources are:

- `pyproject.toml` for docstring convention configuration
- `.pre-commit-config.yaml` for repository hygiene and documentation-adjacent file validation
- strict documentation builds in CI and local rehearsal

Historical guidance remains preserved in:

- `docs/legacy/2026-03-11/docstring_guidelines.md`
- `docs/docstring_guidelines.md`

## When to Update Navigation

Contributors should update `mkdocs.yml` when they:

- add a new canonical page,
- split a chapter into child pages,
- repurpose a top-level section,
- promote a previously implicit topic into a first-class surface.

Because PHIDS builds docs in strict mode, navigation is not optional structure; it is part of the
build contract.

## When to Update API Reference Coverage

Contributors should extend `docs/reference/api.md` when:

- a new public module becomes important to users or contributors,
- a major public-facing package is missing from rendered API docs,
- the module map points to a symbol that is not reachable through the API reference.

## Documentation Build Requirement

All documentation changes should remain compatible with:

```bash
uv run mkdocs build --strict
```

This is a required quality gate, not a best-effort suggestion.

## Practical Contributor Checklist

When adding a new canonical page, a contributor should usually:

1. identify the owning subsystem,
2. read the relevant code and tests,
3. write the page in current-state scientific prose,
4. add cross-links from neighboring chapters,
5. update `mkdocs.yml`,
6. rebuild the docs strictly.

## Common Documentation Pitfalls

### Rewriting history instead of preserving it

Do not silently overwrite historically important documents without archiving their prior role.

### Using legacy intent as present fact

If legacy design and current implementation differ, say so clearly and document the implementation.

### Over-generalizing from one module

A subsystem page should explain ownership boundaries, not imply that one module owns behavior that is
currently split across several modules.

### Treating API docs as narrative docs

`mkdocstrings` is not a substitute for architectural explanation.

## Verified Current-State Evidence

- `docs/information-architecture.md`
- `mkdocs.yml`
- `pyproject.toml`
- `.pre-commit-config.yaml`
- `.github/workflows/ci.yml`
- `docs/reference/`
- `docs/legacy/`

## Where to Read Next

- For contributor workflow and quality gates: [`contribution-workflow-and-quality-gates.md`](contribution-workflow-and-quality-gates.md)
- For whole-project package ownership: [`../reference/module-map.md`](../reference/module-map.md)
- For requirement-to-code coverage: [`../reference/requirements-traceability.md`](../reference/requirements-traceability.md)
- For rendered API docs: [`../reference/api.md`](../reference/api.md)
