---
type: memory
---

## 2024-06-26 - [File Input A11y]
**Learning:** When styling file upload inputs inside `<label>` wrappers with Tailwind, using `hidden` on the `<input>` removes it from the browser focus order entirely, breaking keyboard navigation. This issue was found on the sidebar scenario import.
**Action:** Use `sr-only` instead of `hidden` on the input, and use Tailwind `has-[:focus-visible]:ring-2` on the parent wrapper to proxy the visual focus ring.

## 2025-02-27 - [Load Draft UX]
Learning: The "Load Draft" action for simulation scenarios can be a long-running async operation on the server side, but without `hx-indicator` and `hx-disabled-elt` added to the button, the user receives no immediate feedback leading to potential multiple submissions (which could result in unexpected behaviour or frustration).
Action: Always add an SVG spinner with the `.htmx-indicator` class, `hx-indicator`, and `hx-disabled-elt="this"` to HTMX elements that trigger potentially slow simulation loading or resetting actions.
