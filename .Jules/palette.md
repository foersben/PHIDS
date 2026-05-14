## 2024-05-14 - Accessible Spatial Coordinates in Remove Buttons
**Learning:** For coordinate-based UI lists (like placement grids), generic "Remove" ARIA labels are insufficient for screen reader users who cannot see the spatial layout. Injecting specific entity coordinates (e.g., `(x, y)`) directly into the `aria-label` provides essential context.
**Action:** Always template spatial coordinates into `aria-label` and `title` attributes for spatial entity deletion buttons to assist screen reader users and provide hover context.
