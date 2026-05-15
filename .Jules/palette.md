## 2024-05-15 - [Spatial Coordinates in ARIA Labels]
**Learning:** For delete buttons in coordinate-based UI lists (like placement grids), generic "Delete" labels are insufficient for screen reader users as multiple entities can share the same type. The specific coordinate context is critical.
**Action:** Always include the entity coordinates in the ARIA label (e.g., `aria-label="Remove plant at ({{ p.x }}, {{ p.y }})"`) for spatial/grid components.
