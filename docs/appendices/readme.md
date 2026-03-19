# Repository README Mirror

This appendix is a **brief landing-page mirror** of the root `README.md`, not a second full project
manual. It exists so readers who enter via MkDocs can still orient themselves quickly before jumping
to the more specific chapters.

## PHIDS in one paragraph

PHIDS (Plant-Herbivore Interaction & Defense Simulator) is a deterministic ecosystem simulator for
plant defense, herbivore pressure, signaling, toxins, mycorrhizal relays, and telemetry-rich replay
analysis. The runtime lives under `src/phids/` and combines a data-oriented ECS engine, a
JSON/WebSocket API, and a server-rendered HTMX/Jinja UI.

## Who the project is for

- **Researchers** who need explicit trigger rules, reproducible tick-order semantics, telemetry, and
  replay/export surfaces.
- **Users and scenario authors** who want to configure species/substances, load scenarios, run the
  simulation, and inspect live cells in the browser.
- **Contributors** who need a clear architecture map, workflow policy, and performance-sensitive
  repository rules before editing hot paths.

## Runtime baseline and quick start

PHIDS targets **Python 3.12+** and uses `uv` for environment management.

Live documentation: <https://foersben.github.io/PHIDS/>

```bash
uv sync --all-extras --dev
uv run phids --reload
```

Then open `http://127.0.0.1:8000/`.

## Current workflow policy

- Main CI runs on **pushes to `main`**, **pull requests targeting `main`**, and manual dispatch.
- Expensive automation does **not** run on every branch push and does **not** automatically run on
  `develop`.
- GHCR container publishing runs on **version tags** and manual dispatch.
- Bundled binary publishing remains **tag-driven/manual**.

## High-value next links

- Repository landing page: the root `README.md` in the Git repository
- Documentation home: [`../index.md`](../index.md)
- Architecture overview: [`../architecture.md`](../architecture.md)
- Engine docs: [`../engine/index.md`](../engine/index.md)
- Interface surfaces: [`../interfaces/rest-and-websocket-surfaces.md`](../interfaces/rest-and-websocket-surfaces.md)
- Scenario authoring: [`../scenarios/index.md`](../scenarios/index.md)
- Contributor workflow: [`../development/contribution-workflow-and-quality-gates.md`](../development/contribution-workflow-and-quality-gates.md)
- CI and local rehearsal: [`../development/github-actions-and-local-ci.md`](../development/github-actions-and-local-ci.md)
