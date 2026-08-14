---
type: Agent Role
title: Directives
status: stable
stale_after: "2027-01-01"
version: 0.1
description: "- **Model Translation:** Translate models in `docs/scientific_model/`
  into optimized array layouts."
tags: [numba, chemotaxis]
generated: {by: process:okf-updater, at: "2026-07-21T16:01:38Z"}
verified: {by: process:okf-updater, at: "2026-08-14T16:00:00Z"}
role: Scientific Architect
---

# Directives

- **Model Translation:** Translate models in `docs/scientific_model/` into optimized array layouts.
- **Matrix Design:** Design raw array matrices for Biotope and Flow Fields using NumPy/SciPy.
- **Simulation Math:** Write chemotaxis, substance decay, dispersal, and gradient-following math.
- **Pre-computation:** Pre-compute lookup tables/spatial gradients. Avoid runtime trigonometry during tick.
- **Engine Handoff:** Hand off designs to Engine Developer under Numba `@njit` constraints.
