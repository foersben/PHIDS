## 2024-11-20 - Accessible Delete Buttons
**Learning:** Icon-only action buttons (like "✕" for remove) in server-rendered templates (like HTMX partials) were completely inaccessible to screen readers and lacked hover context for mouse users.
**Action:** Always verify icon-only interactive elements have both `aria-label` and `title` attributes so they are accessible across interaction modalities.
