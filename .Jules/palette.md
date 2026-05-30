## 2026-05-30 - [Accessibility for Delete Buttons in Lists]
**Learning:** Icon-only delete buttons in dynamic lists must have unique ARIA labels detailing what they remove to assist screen reader users (e.g., coordinates), as well as explicit visual focus rings for keyboard navigation.
**Action:** Always include specific context in `aria-label` for list item actions, use `title` for tooltips, and apply `focus:outline-none focus-visible:ring-2` for keyboard accessibility.
