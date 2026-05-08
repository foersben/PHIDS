## 2026-05-08 - [Destructive Action Confirmation]
**Learning:** Icon-only destructive buttons in list views (like "✕" for delete) are easy to misclick and provide no context to screen readers, causing a poor UX and accessibility issues.
**Action:** Always add `aria-label`, `title` for hover tooltips, keyboard focus states (`focus-visible:ring-2`), and user confirmation (`hx-confirm`) on these types of delete buttons.
