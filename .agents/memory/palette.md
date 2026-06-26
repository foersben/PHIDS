---
type: memory
---

## 2024-06-26 - [File Input A11y]
**Learning:** When styling file upload inputs inside `<label>` wrappers with Tailwind, using `hidden` on the `<input>` removes it from the browser focus order entirely, breaking keyboard navigation. This issue was found on the sidebar scenario import.
**Action:** Use `sr-only` instead of `hidden` on the input, and use Tailwind `has-[:focus-visible]:ring-2` on the parent wrapper to proxy the visual focus ring.

## 2026-06-26 - [Accessible HTMX Loading Buttons Without Layout Shift]
**Learning:** When adding `hx-indicator` spinners to buttons containing text and icons, directly appending the spinner can cause severe layout shifting in tightly constrained toolbars (like flex headers).
**Action:** Use a `group` class on the button, place an absolute-positioned spinner div hidden by default, and wrap the button content in a span that transitions to `opacity-0` using `group-[.htmx-request]:opacity-0`. This swaps the text for the spinner perfectly in place without changing the button's dimensions.
