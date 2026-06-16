## 2024-05-18 - [Spatial Context in ARIA Labels]
**Learning:** Delete buttons for spatial coordinate-based entities (like plants or swarms in the placement grid) require coordinate context in their ARIA labels to be meaningful. A generic "Delete" label is insufficient when managing multiple identical entities placed at different locations.
**Action:** Always include spatial coordinates (e.g., `aria-label="Remove plant at ({{ p.x }}, {{ p.y }})"`) when adding `aria-label` attributes to delete buttons for spatial entities in coordinate-based UI lists.
