---
type: memory
---

## 2024-06-26 - [File Input A11y]
**Learning:** When styling file upload inputs inside `<label>` wrappers with Tailwind, using `hidden` on the `<input>` removes it from the browser focus order entirely, breaking keyboard navigation. This issue was found on the sidebar scenario import.
**Action:** Use `sr-only` instead of `hidden` on the input, and use Tailwind `has-[:focus-visible]:ring-2` on the parent wrapper to proxy the visual focus ring.
