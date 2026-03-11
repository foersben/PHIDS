# Reference Guide

The reference section separates human-oriented explanation from symbol-oriented API detail.

## Use This Section When You Need

- exact Python module and symbol documentation,
- schema field details,
- runtime method signatures,
- direct links from prose pages into implementation reference.

## Components of This Section

- `reference/module-map.md` — whole-project package and symbol ownership map.
- `reference/requirements-traceability.md` — current-state mapping from requirements to code, docs, and tests.
- `reference/api.md` — mkdocstrings-backed Python API reference.
- `appendices/readme.md` — mirror of the repository README inside the docs site.
- legacy reference material preserved in `legacy/`.

## Recommended Reading Order

1. Start with `reference/module-map.md` if you need to locate the owning module for a behavior.
2. Use `reference/api.md` when you need exact signatures, fields, or docstrings.
3. Use the narrative chapters elsewhere in the site when you need subsystem meaning or scientific
   interpretation.

## Editorial Rule

Narrative pages should explain *why* the simulator is structured as it is. The reference pages
should explain *what symbols exist* and *how they are declared*.
