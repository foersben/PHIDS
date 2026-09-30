"""Tests for the database UI routes to ensure exceptions do not leak."""

from unittest.mock import patch

import pytest

from phids.analytics.bio_database import BioDatabaseModel
from phids.api.routers.ui.database import api_database_rebuild, api_database_save


@pytest.mark.asyncio
async def test_api_database_save_handles_exception_securely():
    """Test that an exception during save returns a generic error."""
    # Arrange
    payload = BioDatabaseModel(flora={}, herbivores={}, substances={})

    with patch("phids.api.routers.ui.database.open", side_effect=Exception("Secret Exception Details")):
        # Act
        response = await api_database_save(payload)

    # Assert
    assert response.status_code == 400
    assert response.body == b"Failed to save database"
    assert b"Secret Exception Details" not in response.body


@pytest.mark.asyncio
async def test_api_database_rebuild_handles_subprocess_error_securely():
    """Test that an ETL subprocess error returns a generic error."""

    # Arrange
    class MockProcess:
        returncode = 1

        async def communicate(self):
            return b"", b"Secret Subprocess Stderr Leak"

    with patch("asyncio.create_subprocess_exec", return_value=MockProcess()):
        # Act
        response = await api_database_rebuild()

    # Assert
    assert response.status_code == 500
    assert response.body == b"ETL Failed"
    assert b"Secret Subprocess Stderr Leak" not in response.body


@pytest.mark.asyncio
async def test_api_database_rebuild_handles_exception_securely():
    """Test that an exception during rebuild returns a generic error."""
    # Arrange
    with patch("asyncio.create_subprocess_exec", side_effect=Exception("Secret Exception Details")):
        # Act
        response = await api_database_rebuild()

    # Assert
    assert response.status_code == 500
    assert response.body == b"Failed to rebuild database"
    assert b"Secret Exception Details" not in response.body
