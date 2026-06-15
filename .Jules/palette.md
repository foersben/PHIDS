## 2024-05-24 - Accessibility improvements for Placement List

**Learning:** When dealing with icon-only delete buttons in coordinate-based lists (like a grid placement editor), standard `aria-label="Delete"` is insufficient. Using context-rich labels like `Remove plant at ({{ p.x }}, {{ p.y }})` greatly improves screen reader clarity. Furthermore, HTMX-injected buttons need explicit focus states using Tailwind (e.g. `focus:outline-none focus-visible:ring-2 focus-visible:ring-red-500 rounded`) since they might not inherit standard browser button focus styles when swapped in dynamically.

**Action:** Always include spatial/contextual data in `aria-label` and `title` attributes for repeated list actions. Ensure all interactive elements, especially icon buttons, have explicit `focus-visible` styles with a relevant ring color (e.g. `ring-red-500` for destructive actions).
