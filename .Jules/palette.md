
## 2025-02-12 - File Upload Accessibility
**Learning:** When styling file upload inputs inside `<label>` wrappers with Tailwind, `class="hidden"` removes the input from the document flow completely, breaking keyboard navigation.
**Action:** Use `class="sr-only"` on the `<input>` to preserve keyboard focusability, and apply visual focus rings to the wrapper using the `has-[:focus-visible]:<class>` pseudo-class.
