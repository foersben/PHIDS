## 2024-05-10 - [HTMX Confirmation Dialogs in Playwright]
**Learning:** When using Playwright to verify HTMX UI actions that trigger native browser dialogs (such as those using `hx-confirm`), Playwright will auto-dismiss the dialog by default. This causes the test to fail silently (e.g., waiting for an element that never updates because the delete action was cancelled).
**Action:** Explicitly configure the Playwright page to accept the dialog (`page.on("dialog", lambda dialog: dialog.accept())`) before clicking the element that triggers the `hx-confirm` prompt.
