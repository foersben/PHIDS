## 2024-04-23 - Icon-Only Buttons Missing ARIA Labels
**Learning:** Found that multiple icon-only deletion buttons (e.g. "✕" in placement_list.html) are missing `aria-label` attributes, making them inaccessible to screen readers, and lacking clear keyboard focus states.
**Action:** Adding `aria-label` to these buttons and using `focus-visible:` utilities to improve keyboard navigation feedback.
