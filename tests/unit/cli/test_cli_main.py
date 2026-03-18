"""Tests for the PHIDS command-line entry point.

This module validates the runtime launcher implemented in
:mod:`phids.__main__`. The tests ensure that parser defaults remain stable and
that :func:`phids.__main__.main` forwards parsed arguments to ``uvicorn.run``
without mutating simulation state, preserving deterministic startup semantics
for API, HTMX, and WebSocket surfaces.
"""

from __future__ import annotations


def test_build_parser_defaults_are_stable() -> None:
    """Parser defaults stay aligned with documented local development startup."""
    from phids.__main__ import build_parser

    parser = build_parser()
    args = parser.parse_args([])

    assert args.host == "127.0.0.1"
    assert args.port == 8000
    assert args.reload is False
    assert args.log_level == "info"


def test_main_passes_cli_args_to_uvicorn(monkeypatch) -> None:
    """CLI main forwards host/port/reload/log-level arguments to uvicorn.run."""
    import phids.__main__ as cli

    calls: dict[str, object] = {}

    def _fake_run(app: object, **kwargs: object) -> None:
        calls["app"] = app
        calls.update(kwargs)

    import uvicorn

    monkeypatch.setattr(uvicorn, "run", _fake_run)

    cli.main(["--host", "0.0.0.0", "--port", "9001", "--reload", "--log-level", "debug"])

    assert calls["host"] == "0.0.0.0"
    assert calls["port"] == 9001
    assert calls["reload"] is True
    assert calls["log_level"] == "debug"
    assert calls["app"] is not None
