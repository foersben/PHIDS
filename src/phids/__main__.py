"""Command-line entry point for the PHIDS runtime server.

This module defines the process boundary between operating-system invocation and the PHIDS API runtime. It formalizes host, port, reload, and logging controls so simulation services can be started reproducibly across local development and containerized deployments. The launcher delegates execution to the FastAPI surface without mutating simulation state, preserving deterministic behavior in downstream ECS and double-buffered engine phases.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence

_VALID_LOG_LEVELS = ("critical", "error", "warning", "info", "debug", "trace")


def build_parser() -> argparse.ArgumentParser:
    """Construct the PHIDS command-line parser for server bootstrap.

    The parser encodes operational parameters that influence network exposure and observability of the runtime process. Centralizing these flags constrains startup variability and supports reproducible execution conditions for API, HTMX, and WebSocket interfaces.

    Returns:
        Configured parser for launching the PHIDS server process.
    """
    parser = argparse.ArgumentParser(
        prog="phids",
        description=(
            "Run the PHIDS FastAPI server that powers the JSON API, HTMX UI, "
            "and WebSocket simulation streams."
        ),
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Interface to bind the HTTP server to. Use 0.0.0.0 inside containers.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="TCP port for the FastAPI server.",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for local development.",
    )
    parser.add_argument(
        "--log-level",
        default="info",
        choices=_VALID_LOG_LEVELS,
        help="Uvicorn log verbosity.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    """Start the PHIDS FastAPI application with parsed runtime arguments.

    This function materializes command-line intent into a concrete ASGI server configuration. It resolves arguments, loads the API application, and transfers control to Uvicorn for long-running service orchestration.

    Args:
        argv: Optional argument sequence used by tests or embedding contexts.

    Returns:
        None. The function starts the server process and does not produce a data value.
    """
    args = build_parser().parse_args(argv)

    import uvicorn
    from phids.api.main import app

    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level,
    )


if __name__ == "__main__":
    main()
