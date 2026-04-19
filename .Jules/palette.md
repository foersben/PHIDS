## 2026-04-19 - Missing ARIA Labels on Icon-Only Buttons
**Learning:** Found an accessibility issue pattern where icon-only buttons (like "✕" for delete or "⟩" for expand) are using character symbols without `aria-label` attributes, relying sometimes only on visual context or `title` attributes.
**Action:** Always verify that buttons containing only symbols or icons have an explicit `aria-label` attribute to provide proper context for screen readers.
