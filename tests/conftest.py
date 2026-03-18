"""Shared pytest fixtures for PHIDS test modules.

This fixture module provides lightweight, reusable ECS and biotope constructors
so unit and integration suites can avoid repetitive setup boilerplate while
preserving deterministic state isolation per test invocation.
"""

from __future__ import annotations

import pytest

from phids.engine.core.biotope import GridEnvironment
from phids.engine.core.ecs import ECSWorld


@pytest.fixture
def empty_world() -> ECSWorld:
    """Return a fresh ECS world with no entities registered."""
    return ECSWorld()


@pytest.fixture
def standard_biotope() -> GridEnvironment:
    """Return a deterministic 50x50 environment with two signal and toxin layers."""
    return GridEnvironment(width=50, height=50, num_signals=2, num_toxins=2)
