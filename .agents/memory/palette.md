---
type: memory
---

## 2026-06-30 - [Accessibility: Nested Form Components]
**Learning:** Deeply nested form elements in HTMX UI configurations (like trigger rules) often miss standardized focus states, causing navigation confusion for keyboard users.
**Action:** When constructing or modifying form nodes, add explicit focus rings (e.g., `focus:outline-none focus-visible:ring-2`) for all interactive elements and dynamic ARIA labels for repetitive actions (e.g., delete buttons per row).
