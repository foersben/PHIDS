## 2024-05-23 - Contextual ARIA labels for spatial UI lists
**Learning:** Adding coordinates to aria-labels (e.g. `aria-label="Remove plant at ({{ p.x }}, {{ p.y }})"`) for delete buttons in coordinate-based lists makes the action clear to screen readers when there are multiple similar entities.
**Action:** When working on lists that map to spatial or coordinate-based entities, always include the specific spatial context in ARIA attributes for destructive or action buttons.
