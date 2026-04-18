"""Integration tests for malformed JSON parsing in activation conditions.

This module verifies that the API correctly handles and rejects invalid JSON strings
provided for activation conditions in trigger rules, ensuring robust error handling
at the API boundary.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from phids.api.main import app
from phids.api.ui_state import reset_draft


@pytest.fixture(autouse=True)
def _reset_state() -> None:
    """Reset the global draft state before each test to ensure isolation."""
    reset_draft()


@pytest.fixture
def _client() -> AsyncClient:
    """Provide an asynchronous test client for the FastAPI application."""
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_add_trigger_rule_with_malformed_json(_client: AsyncClient) -> None:
    """Verifies that POST /api/config/trigger-rules rejects malformed condition JSON.

    The API should return a 400 Bad Request when the 'activation_condition_json'
    field contains a string that is not valid JSON.
    """
    async with _client as client:
        response = await client.post(
            "/api/config/trigger-rules",
            data={
                "flora_species_id": 0,
                "predator_species_id": 0,
                "substance_id": 0,
                "min_predator_population": 5,
                "activation_condition_json": "{ invalid json",
            },
        )

    assert response.status_code == 400
    assert "Invalid condition JSON" in response.json()["detail"]


@pytest.mark.asyncio
async def test_update_trigger_rule_with_malformed_json(_client: AsyncClient) -> None:
    """Verifies that PUT /api/config/trigger-rules/{index} rejects malformed condition JSON.

    The API should return a 400 Bad Request when updating a trigger rule with
    an invalid JSON string for the activation condition.
    """
    # First, add a valid rule so we have something to update
    async with _client as client:
        await client.post(
            "/api/config/trigger-rules",
            data={
                "flora_species_id": 0,
                "predator_species_id": 0,
                "substance_id": 0,
                "min_predator_population": 5,
                "activation_condition_json": "",
            },
        )

        # Now try to update it with malformed JSON
        response = await client.put(
            "/api/config/trigger-rules/0",
            data={
                "activation_condition_json": '{"kind": "enemy_presence", "invalid": }',
            },
        )

    assert response.status_code == 400
    assert "Invalid condition JSON" in response.json()["detail"]
