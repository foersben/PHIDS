## 2024-05-15 - Missing accessibility on dynamic list items
**Learning:** Found a pattern of missing `aria-label`, `title`, and explicit `focus-visible` styles on icon-only action buttons (like delete '✕') within dynamically generated lists (e.g., entity placements). These are easy to overlook compared to static structural components.
**Action:** Always verify that loop-generated inline icon buttons receive full accessibility attributes and keyboard focus styling, especially when they represent destructive actions like deletion.
