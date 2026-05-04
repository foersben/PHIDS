## 2026-05-04 - Icon-Only Deletion Buttons Lack Confirmations & A11y
**Learning:** Icon-only deletion buttons for placed entities (plants/swarms) often miss destructive action confirmations (`hx-confirm`), `aria-label`s, and proper keyboard focus states, making them prone to accidental clicks and hard to use for screen reader/keyboard users.
**Action:** Always add `aria-label`, `title`, explicit focus styles (e.g., `focus:outline-none focus-visible:ring-2`), and `hx-confirm` dialogs to any icon-only delete buttons in configuration lists.
