## 2026-06-03 - Adding accessibility labels and focus states to dynamic list items
**Learning:** When adding `aria-label` attributes to delete buttons for spatial entities in coordinate-based UI lists, dynamically including the specific grid coordinates (e.g., `Remove plant at (x, y)`) makes the list much more accessible. Focus states (via `focus-visible`) enhance keyboard navigability without degrading pointer UX.
**Action:** Ensure dynamic contexts like coordinates are consistently appended to ARIA labels on list item actions to prevent ambiguity.
