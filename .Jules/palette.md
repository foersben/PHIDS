## 2024-06-11 - [UX] Spatial Context in Delete Labels
**Learning:** When dealing with coordinate-based list items (like placements on a grid), generic 'Delete' or 'Remove' aria-labels are insufficient. Screen reader users lack the visual map context to know which item is being deleted if there are multiple items of the same type.
**Action:** Always inject specific spatial coordinates or unique identifiers into the `aria-label` (e.g., `aria-label="Remove plant at ({{ p.x }}, {{ p.y }})"`) for lists representing spatial configurations.
