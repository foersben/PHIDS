
## 2024-05-26 - Spatial coordinates for list accessibility
**Learning:** When dealing with coordinate-based UI lists (like the placement grid entities), screen readers encounter multiple "Delete" buttons in a row. Using list indices for `aria-label`s isn't descriptive enough.
**Action:** Always include the specific spatial context/coordinates in the `aria-label` (e.g., `aria-label="Remove plant at ({{ p.x }}, {{ p.y }})"`) to disambiguate identical icon-only buttons in coordinate-based systems.
