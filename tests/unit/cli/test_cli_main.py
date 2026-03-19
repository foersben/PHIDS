"""Tests for the PHIDS command-line entry point.

This module validates the runtime launcher implemented in
:mod:`phids.__main__`. The tests ensure that Typer option defaults remain
stable and that :func:`phids.__main__.main` forwards validated arguments to the
server dispatch boundary without mutating simulation state, preserving
deterministic startup semantics for API, HTMX, and WebSocket surfaces.
"""

from __future__ import annotations

import pytest


def test_cli_default_options_are_stable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Typer default options route to the documented local development server configuration."""
    import phids.__main__ as cli

    calls: dict[str, object] = {}

    def _fake_run_server(*, host: str, port: int, reload: bool, log_level: str) -> None:
        calls.update({"host": host, "port": port, "reload": reload, "log_level": log_level})

    monkeypatch.setattr(cli, "_run_server", _fake_run_server)
    cli.main([])

    assert calls["host"] == "127.0.0.1"
    assert calls["port"] == 8000
    assert calls["reload"] is False
    assert calls["log_level"] == "info"


def test_main_passes_cli_args_to_uvicorn(monkeypatch) -> None:
    """CLI main forwards host/port/reload/log-level options to the server dispatch boundary."""
    import phids.__main__ as cli

    calls: dict[str, object] = {}

    def _fake_run_server(*, host: str, port: int, reload: bool, log_level: str) -> None:
        calls.update({"host": host, "port": port, "reload": reload, "log_level": log_level})

    monkeypatch.setattr(cli, "_run_server", _fake_run_server)

    cli.main(["--host", "0.0.0.0", "--port", "9001", "--reload", "--log-level", "debug"])

    assert calls["host"] == "0.0.0.0"
    assert calls["port"] == 9001
    assert calls["reload"] is True
    assert calls["log_level"] == "debug"


def test_main_rejects_invalid_log_level() -> None:
    """CLI exits with a usage error when the log level is outside the configured enum."""
    import click
    import phids.__main__ as cli

    with pytest.raises(click.BadParameter):
        cli.main(["--log-level", "verbose"])


def test_run_server_uses_import_string_for_reload(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reload mode passes an import-string app target so Uvicorn can spawn the reloader process."""
    import phids.__main__ as cli

    captured: dict[str, object] = {}

    def _fake_run(app: object, **kwargs: object) -> None:
        captured["app"] = app
        captured.update(kwargs)

    import uvicorn

    monkeypatch.setattr(uvicorn, "run", _fake_run)
    cli._run_server(host="127.0.0.1", port=8000, reload=True, log_level="info")

    assert captured["app"] == "phids.api.main:app"
    assert captured["reload"] is True
