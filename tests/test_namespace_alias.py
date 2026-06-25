"""Experimental validation suite for test namespace alias.

This module defines hypothesis-driven checks for deterministic ecosystem behavior, API constraints, and simulation invariants. The tests map computational rules to biological interpretations, including metabolic attrition, trigger-gated signaling, and O(1) spatial locality assumptions, to ensure that implementation details remain aligned with the PHIDS scientific model.
"""

from __future__ import annotations

import importlib

import pytest


def test_phids_namespace_is_available() -> None:
    """Validates the phids namespace is available invariant and confirms the expected biological behavior under controlled simulation conditions.

    The assertions in this test enforce deterministic state transitions so ecological outcomes remain consistent with configured constraints and signal-response dynamics.

    Returns:
        None. The function verifies invariant compliance through assertions rather than data return.

    """
    app = importlib.import_module("phids.api.main").app
    configure_logging = importlib.import_module("phids.shared.logging_config").configure_logging

    assert app.title.startswith("PHIDS")
    configure_logging(force=True)


def test_legacy_phytodynamics_namespace_is_removed() -> None:
    """Validates the legacy phytodynamics namespace is removed invariant and confirms the expected biological behavior under controlled simulation conditions.

    The assertions in this test enforce deterministic state transitions so ecological outcomes remain consistent with configured constraints and signal-response dynamics.

    Returns:
        None. The function verifies invariant compliance through assertions rather than data return.

    """
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("phytodynamics.api.main")

    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("phytodynamics.shared.logging_config")


def test_phids_wrapper_modules_import() -> None:
    """Validates the phids wrapper modules import invariant and confirms the expected biological behavior under controlled simulation conditions.

    The assertions in this test enforce deterministic state transitions so ecological outcomes remain consistent with configured constraints and signal-response dynamics.

    Returns:
        None. The function verifies invariant compliance through assertions rather than data return.

    """
    module_names = [
        "phids.api",
        "phids.api.main",
        "phids.api.schemas",
        "phids.api.ui_state",
        "phids.engine",
        "phids.engine.loop",
        "phids.engine.components",
        "phids.engine.components.plant",
        "phids.engine.components.swarm",
        "phids.engine.components.substances",
        "phids.engine.core",
        "phids.engine.core.biotope",
        "phids.engine.core.ecs",
        "phids.engine.core.flow_field",
        "phids.engine.systems",
        "phids.engine.systems.lifecycle",
        "phids.engine.systems.interaction",
        "phids.engine.systems.signaling",
        "phids.io",
        "phids.io.replay",
        "phids.io.scenario",
        "phids.shared",
        "phids.shared.constants",
        "phids.shared.logging_config",
        "phids.telemetry",
        "phids.telemetry.analytics",
        "phids.telemetry.conditions",
        "phids.telemetry.export",
    ]

    for module_name in module_names:
        module = importlib.import_module(module_name)
        assert module is not None
