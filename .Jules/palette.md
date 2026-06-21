## 2026-06-21 - Spatial Context in ARIA Labels
**Learning:** When adding `aria-label` attributes to delete buttons for spatial entities in coordinate-based UI lists (like placement grids), standard labels like 'Delete item' are insufficient. They lack the spatial context needed for screen reader users to distinguish between identical entity types placed at different coordinates.
**Action:** Always include the specific spatial context/coordinates in the label (e.g., `aria-label="Remove plant at ({{ p.x }}, {{ p.y }})"`) when dealing with coordinate-based or grid placement lists.
