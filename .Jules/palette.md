## 2026-06-04 - [Add spatial context to coordinate-based ARIA labels]
**Learning:** When adding `aria-label` attributes to delete buttons for spatial entities in coordinate-based UI lists (like placement grids), using generic labels like "Remove plant" is insufficient. Screen reader users lack the visual context of the coordinate grid to distinguish between multiple identical entity types.
**Action:** Always include the specific spatial context/coordinates in the label (e.g., `aria-label="Remove plant at ({{ p.x }}, {{ p.y }})"`) to assist screen reader users.
