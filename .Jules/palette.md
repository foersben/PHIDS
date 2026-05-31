## 2024-05-31 - Spatial Context in ARIA Labels for Grid Entities
**Learning:** When adding `aria-label` attributes to delete buttons for spatial entities in coordinate-based UI lists (like the placement grid), standard "Delete" labels lack context. Users relying on screen readers need to know *which* specific entity they are removing, especially when many exist.
**Action:** Always include the specific spatial context/coordinates in the label (e.g., `aria-label="Remove plant at ({{ p.x }}, {{ p.y }})"`) to assist screen reader users.
