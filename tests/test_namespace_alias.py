from __future__ import annotations

import importlib

import pytest


def test_phids_namespace_is_available() -> None:
    app = importlib.import_module("phids.api.main").app
    configure_logging = importlib.import_module("phids.shared.logging_config").configure_logging

    assert app.title.startswith("PHIDS")
    configure_logging(force=True)


def test_legacy_phytodynamics_namespace_is_removed() -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("phytodynamics.api.main")

    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("phytodynamics.shared.logging_config")


def test_phids_wrapper_modules_import() -> None:
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
