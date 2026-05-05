from playwright.sync_api import sync_playwright
import time

def test_ui():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto('http://127.0.0.1:8000')

        # Verify Import JSON label is accessible and input is sr-only
        input_el = page.locator('#scenario-import-input')
        assert input_el.evaluate('el => el.classList.contains("sr-only")'), "File input should be sr-only"

        # Verify the diagnostic buttons
        # Ensure that they have the new aria-label attributes
        btn_model = page.locator('.diagnostics-tab-collapsed[data-tab-key="model"]')
        assert btn_model.get_attribute('aria-label') == "Model diagnostics"
        btn_frontend = page.locator('.diagnostics-tab-collapsed[data-tab-key="frontend"]')
        assert btn_frontend.get_attribute('aria-label') == "Frontend diagnostics"
        btn_backend = page.locator('.diagnostics-tab-collapsed[data-tab-key="backend"]')
        assert btn_backend.get_attribute('aria-label') == "Backend logs"
        btn_expand = page.locator('#diagnostics-expand-collapsed')
        assert btn_expand.get_attribute('aria-label') == "Expand diagnostics"

        print("UI tests passed!")
        browser.close()

if __name__ == '__main__':
    test_ui()
