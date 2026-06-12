
## 2024-06-12 - Spatial Context in ARIA Labels
**Learning:** When adding ARIA labels to generic "Delete" buttons (e.g., an "X" icon) in coordinate-based UIs (like the placement editor lists), simply stating "Delete plant" is insufficient for screen reader users because they lose the visual association with the row's coordinates. Injecting the spatial coordinates directly into the label (e.g., `aria-label="Remove plant at ({{ p.x }}, {{ p.y }})"`) restores crucial context.
**Action:** Always include specific identifying context (like entity names, IDs, or spatial coordinates) in ARIA labels for repetitive actions in list views to ensure screen reader users understand exactly which item they are interacting with.
