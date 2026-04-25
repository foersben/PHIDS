## 2026-04-25 - Add aria-labels to icon-only buttons
**Learning:** Found several icon-only interactive elements (like the plant/swarm delete buttons and diagnostic tab/collapse toggles) that lacked proper accessible names, making them difficult for screen readers to interpret.
**Action:** Added `aria-label` attributes mirroring visual/title context to these elements, ensuring screen reader compatibility and clearer intent.
