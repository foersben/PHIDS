---
type: Agent Memory
title: Current Architecture State (June 2026)
status: stable
stale_after: "2027-01-01"
version: 0.1
description: "- **Python:** Migrating to 3.13."
tags: [chemotaxis, python]
generated: {by: process:okf-updater, at: "2026-07-21T16:01:38Z"}
verified: {by: process:okf-updater, at: "2026-08-14T16:00:00Z"}
---

## Infrastructure Upgrade in Progress

- **Python:** Migrating to 3.13.
- **Dependency Management:** Transitioned to `uv` (replacing legacy requirements/Hatch pure reliance).
- **Documentation:** Transitioned from standard MkDocs to Zensical.
- **Scientific Model:** The core scientific documentation (`chemotaxis.md`, `reaction_diffusion.md`) is currently stashed on the `docs/scientific-model-overhaul` branch pending the completion of the `develop` branch infrastructure deep-clean.
