# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Integration tests for telemetry routing and payload parsing.

This module provides targeted coverage for branches within telemetry and config
routes that are difficult to reach in broad end-to-end tests, such as strict type
validation, absent-loop exception handling, and malformed condition payloads.
"""

from __future__ import annotations

import typing

import pytest

if typing.TYPE_CHECKING:
    from httpx import AsyncClient

from phids.api import main as api_main
from phids.api.ui_state import get_draft


@pytest.mark.asyncio
async def test_telemetry_export_routes_absent_loop(api_client: AsyncClient) -> None:
    """Validate that CSV and JSON export routes raise 400 when no loop is loaded."""
    api_main._sim_loop = None

    response_csv = await api_client.get("/api/telemetry/export/csv")
    assert response_csv.status_code == 400
    assert "No scenario loaded" in response_csv.text

    response_json = await api_client.get("/api/telemetry/export/json")
    assert response_json.status_code == 400
    assert "No scenario loaded" in response_json.text


@pytest.mark.asyncio
async def test_config_trigger_rule_malformed_json_condition(api_client: AsyncClient) -> None:
    """Validate robust error handling when receiving malformed JSON conditions.

    Verifies the `json.JSONDecodeError` handling in `_parse_activation_condition_json`.
    """
    draft = get_draft()
    draft.trigger_rules.clear()

    # Payload missing trailing brace
    malformed_json = '{"kind": "herbivore_presence"'

    response = await api_client.post(
        "/api/config/trigger-rules",
        data={
            "flora_species_id": 0,
            "herbivore_species_id": 0,
            "substance_id": 0,
            "min_herbivore_population": 1,
            "activation_condition_json": malformed_json,
        },
    )

    assert response.status_code == 400
    assert "Invalid condition JSON" in response.text


@pytest.mark.asyncio
async def test_config_trigger_rule_invalid_schema_condition(api_client: AsyncClient) -> None:
    """Validate robust error handling for valid JSON that fails Pydantic schema validation.

    Verifies the `ValidationError` handling in `_parse_activation_condition_json`.
    """
    draft = get_draft()
    draft.trigger_rules.clear()

    # Syntactically valid JSON, but missing required 'kind' field
    invalid_schema_json = '{"some_other_field": 123}'

    response = await api_client.post(
        "/api/config/trigger-rules",
        data={
            "flora_species_id": 0,
            "herbivore_species_id": 0,
            "substance_id": 0,
            "min_herbivore_population": 1,
            "activation_condition_json": invalid_schema_json,
        },
    )

    assert response.status_code == 400
    assert "Invalid activation condition" in response.text


@pytest.mark.asyncio
async def test_export_timeseries_strict_type_enforcement(api_client: AsyncClient) -> None:
    """Validate that Pydantic enforces strict types on the /api/export/{data_type} endpoint.

    Submitting a non-coercible string for `tick_interval` should result in a 422 Unprocessable Entity.
    """
    response = await api_client.get(
        "/api/export/timeseries",
        params={
            "format": "csv",
            "tick_interval": "not_an_integer",
        },
    )

    # FastAPI/Pydantic returns 422 for path/query param validation failures
    assert response.status_code == 422
