## 2026-05-29 - [Spatial Context in ARIA Labels]
**Learning:** When listing entities that are placed on a coordinate grid, generic "Delete" labels on icon-only buttons fail to provide enough context for screen reader users to distinguish between multiple identical items.
**Action:** Always inject spatial coordinates (e.g., `x`, `y`) directly into the `aria-label` for list items derived from a spatial canvas.
