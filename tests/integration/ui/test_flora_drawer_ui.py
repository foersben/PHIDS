# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Integration test for Flora Species configuration UI with tiered progressive drawer."""

from __future__ import annotations

import pytest
from bs4 import BeautifulSoup
from fastapi.testclient import TestClient

from phids.api.main import app
from phids.api.schemas.species import FloraSpeciesParams
from phids.api.ui_state.state import get_draft


@pytest.fixture
def client() -> TestClient:
    """Return a test client."""
    return TestClient(app)


def test_ui_flora_tiered_drawer_structure(client: TestClient) -> None:
    """Verify that the Flora Species view renders primary table columns and drawers."""
    # Ensure draft has at least one flora species
    draft = get_draft()
    if not draft.flora_species:
        draft.flora_species.append(
            FloraSpeciesParams(
                species_id=0,
                name="TestFlora",
                base_energy=10.0,
                max_energy=100.0,
                growth_rate=5.0,
                survival_threshold=1.0,
                reproduction_interval=10,
                structural_mass_max=50.0,
                structural_growth_rate=0.015,
                seed_energy_cost=4.0,
                seed_max_dist=3.5,
            )
        )

    response = client.get("/ui/flora")
    assert response.status_code == 200

    html = response.text
    soup = BeautifulSoup(html, "html.parser")

    # 1. Assert table headers include the essential columns
    headers = [th.get_text(strip=True) for th in soup.find_all("th")]
    assert "Base E" in headers
    assert "Max E" in headers
    assert "Growth" in headers
    assert "Surv. Thr." in headers
    assert "Max Struct" in headers
    assert "Repr. Int." in headers
    assert "Seed Cost" in headers
    assert "Disp. Dist" in headers
    assert "Camo" in headers
    assert "Details" in headers

    # 2. Assert tbody group and drawer exist for species 0
    assert soup.find("tbody", id="flora-group-0") is not None
    assert soup.find("tr", id="flora-row-0") is not None
    drawer = soup.find("tr", id="flora-drawer-0")
    assert drawer is not None
    assert "hidden" in drawer.get("class", [])

    # 3. Assert drawer content contains all 3 panels and ecosystem shortcuts
    content = soup.find(id="flora-drawer-content-0")
    assert content is not None
    text = content.get_text()
    assert "Structural Lignification" in text
    assert "Seed Aerodynamics & Dispersal" in text
    assert "Symbiosis & Transport" in text
    assert "Implicit Ecosystem Boundaries" in text

    # 4. Assert bottom info guide box exists with 4 core sections
    info_box = soup.find("h3", string=lambda s: s and "Flora Species & Autotrophic Growth Guide" in s)
    assert info_box is not None
    assert "Autotrophy & Dual-Proxy" in html
    assert "Seed Dispersal & Anemochory" in html
    assert "Symbiosis & Phloem Kinetics" in html
    assert "Implicit Ecosystem Boundaries" in html

    # 5. Assert authentic TeX formulas are properly declared for KaTeX rendering
    assert r"$M_{\text{structural}}$" in html
    assert r"$g_M$" in html
    assert r"$E_{\text{max}}$" in html
    assert r"$\tau_{\text{link}}$" in html
    assert r"$\text{Intake} \ge \text{Upkeep}$" in html


def test_ui_katex_integration_in_base(client: TestClient) -> None:
    """Verify that base.html loads KaTeX assets and registers HTMX auto-render hooks."""
    response = client.get("/")
    assert response.status_code == 200

    html = response.text
    # Assert KaTeX stylesheet and scripts are loaded
    assert "katex.min.css" in html
    assert "katex.min.js" in html
    assert "auto-render.min.js" in html

    # Assert global renderAllMath function and HTMX listeners exist
    assert "renderAllMath" in html
    assert "renderMathInElement" in html
    assert "htmx:afterSwap" in html
    assert "htmx:afterSettle" in html


def test_ui_dse_guide_title(client: TestClient) -> None:
    """Verify that the DSE panel renders the canonical guide title and KaTeX formula."""
    response = client.get("/ui/dse")
    assert response.status_code == 200
    html = response.text
    assert "Design Space Exploration (DSE) & Pareto Optimization Guide" in html
    assert "Differential Stability Explorer" not in html
    assert r"$Z_2 - Z_7$" in html
