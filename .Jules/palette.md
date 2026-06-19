
## 2024-06-19 - Adding Context to Coordinate-Based Deletions
**Learning:** For lists of spatial entities (like plants and swarms on a grid), "Delete" or "✕" labels on buttons are insufficiently descriptive for screen readers since there can be multiple identical entities.
**Action:** When adding `aria-label` attributes to delete buttons for spatial entities in coordinate-based UI lists, always include the specific spatial context/coordinates in the label (e.g., `aria-label="Remove plant at ({{ p.x }}, {{ p.y }})"`) to assist screen reader users. Also ensure focus styles are explicit (e.g. `focus-visible:ring-2`) for HTMX-injected buttons.
