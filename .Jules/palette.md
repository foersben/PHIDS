## 2024-05-17 - Contextual ARIA labels in dynamic grids
**Learning:** Adding context (like coordinates) to ARIA labels and tooltips in grid-based lists (like placement editors) makes them significantly more useful for screen reader users than a generic label.
**Action:** Always interpolate coordinate data into attributes like `aria-label` and `hx-confirm` for elements inside spatial data lists.
