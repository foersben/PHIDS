## 2024-10-24 - Contextual Aria Labels in Coordinate Lists
**Learning:** In coordinate-based UI lists (like grid placement editors), generic "Delete" ARIA labels are insufficient. Screen reader users need the spatial context (e.g., coordinates) included directly in the label to confidently identify which spatial entity they are removing.
**Action:** Always include specific coordinates or defining spatial attributes in `aria-label`s for actions within spatial lists (e.g., `aria-label="Remove plant at (x, y)"`).
