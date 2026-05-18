## 2024-05-18 - [Targeting Valid Routes for Frontend Tests]
**Learning:** Navigating to assumed aggregate endpoints like `/ui/draft/config` during Playwright verification leads to 404s. The application structures UI views under specific, individual routes (e.g., `/ui/placements`, `/ui/flora`) rather than a single unified config page.
**Action:** Always verify the correct routing structure using the FastAPI app directly (e.g., `print([r.path for r in app.routes])`) before scripting navigation in verification tasks.
