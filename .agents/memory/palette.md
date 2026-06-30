---
type: memory
---

## 2024-06-26 - [File Input A11y]
**Learning:** When styling file upload inputs inside `<label>` wrappers with Tailwind, using `hidden` on the `<input>` removes it from the browser focus order entirely, breaking keyboard navigation. This issue was found on the sidebar scenario import.
**Action:** Use `sr-only` instead of `hidden` on the input, and use Tailwind `has-[:focus-visible]:ring-2` on the parent wrapper to proxy the visual focus ring.

## 2024-06-30 - [Loading Button Text Wrapping]
**Learning:** Adding an inline SVG spinner element to an HTMX button (e.g., using `.htmx-indicator`) can alter the button's layout width during the loading state, causing the button text to wrap to a new line and briefly change the button height.
**Action:** Always add the `whitespace-nowrap` Tailwind class to the `inline-flex` wrapper spanning the spinner and text (e.g., `<span class="inline-flex items-center whitespace-nowrap">`) to maintain a single-line layout and prevent layout shifts during asynchronous state changes.
