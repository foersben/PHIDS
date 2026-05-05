## 2026-05-05 - Accessible File Upload Inputs Inside Labels
**Learning:** Tailwind's `hidden` class sets `display: none`, completely removing elements like file inputs from the keyboard tab order. Screen reader users and keyboard users cannot interact with it.
**Action:** Use `class="sr-only"` for the hidden file input so it remains keyboard-focusable. On the parent `<label>`, use the `has-[:focus-visible]:...` pseudo-class (e.g. `has-[:focus-visible]:ring-2`) to apply visual focus rings around the label when the invisible input inside it receives focus.
