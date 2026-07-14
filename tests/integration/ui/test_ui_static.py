# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Test UI static content serving."""

import subprocess
import tempfile

import pytest
from bs4 import BeautifulSoup
from fastapi.testclient import TestClient

from phids.api.main import app


@pytest.fixture
def client() -> TestClient:
    """Return a test client."""
    return TestClient(app)


def test_ui_database_dashboard_structure(client: TestClient) -> None:
    """Test that the database dashboard renders correctly and contains required elements."""
    response = client.get("/ui/database")
    assert response.status_code == 200

    html = response.text
    soup = BeautifulSoup(html, "html.parser")

    # 1. Assert tabs are present
    assert soup.find(id="tab-btn-flora") is not None
    assert soup.find(id="tab-btn-herbivores") is not None
    assert soup.find(id="tab-btn-substances") is not None

    # 2. Assert content areas are present
    assert soup.find(id="tab-content-flora") is not None
    assert soup.find(id="tab-content-herbivores") is not None
    assert soup.find(id="tab-content-substances") is not None

    # 3. Assert editor modal is present
    assert soup.find(id="modal-editor") is not None
    assert soup.find(id="edit-category") is not None

    # 4. Assert form sections are present
    assert soup.find(id="form-flora-props") is not None
    assert soup.find(id="form-herbivore-props") is not None
    assert soup.find(id="form-substance-props") is not None

    # 5. Assert right-side rules builder is present
    assert soup.find(id="rules-container") is not None


def test_ui_database_dashboard_js_syntax(client: TestClient) -> None:
    """Extract Javascript blocks from the rendered HTML and validate syntax via node -c."""
    response = client.get("/ui/database")
    assert response.status_code == 200

    soup = BeautifulSoup(response.text, "html.parser")
    scripts = soup.find_all("script")

    # We want to validate executable scripts (not application/json)
    executable_scripts = [
        s.string for s in scripts if s.string and not s.get("type", "").startswith("application/json")
    ]

    for idx, js_code in enumerate(executable_scripts):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=True) as temp_js:
            temp_js.write(js_code)
            temp_js.flush()

            # Run node -c (Check syntax without executing)
            try:
                subprocess.run(
                    ["node", "-c", temp_js.name],
                    check=True,
                    capture_output=True,
                    text=True,
                )
            except subprocess.CalledProcessError as e:
                pytest.fail(
                    f"Javascript syntax error detected in script block {idx}:\n{e.stderr}\n\n"
                    f"Code snippet:\n{js_code[:500]}..."
                )
