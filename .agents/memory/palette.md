---
type: memory
---

## 2024-06-26 - [File Input A11y]
**Learning:** When styling file upload inputs inside `<label>` wrappers with Tailwind, using `hidden` on the `<input>` removes it from the browser focus order entirely, breaking keyboard navigation. This issue was found on the sidebar scenario import.
**Action:** Use `sr-only` instead of `hidden` on the input, and use Tailwind `has-[:focus-visible]:ring-2` on the parent wrapper to proxy the visual focus ring.

## 2024-06-29 - [HTMX Async State UI Standardization]
**Learning:** For long-running HTMX actions (like "Reset" and "Load Draft" which rebuild the draft state and simulation), the lack of immediate visual feedback leads to double-submissions and poor perceived performance.
**Action:** Standardize async button feedback by adding `hx-indicator`, `hx-disabled-elt="this"`, an inline SVG spinner (with `.htmx-indicator`), and Tailwind classes `inline-flex items-center disabled:opacity-50` to provide immediate, accessible feedback during server processing.
