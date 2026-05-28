
## 2026-05-28 - [Add ARIA labels and focus styles to placement delete buttons]
**Learning:** In dynamically generated placement lists with multiple entities (like plants and swarms), generic icon-only delete buttons are inaccessible to screen readers and difficult to navigate via keyboard.
**Action:** Add descriptive `aria-label` attributes containing specific spatial coordinates to differentiate identically looking delete buttons in repeated lists. Also, include `focus-visible:ring` styles to improve keyboard navigation visibility without altering default click appearances.
