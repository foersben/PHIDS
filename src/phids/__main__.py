"""Command-line launcher for the PHIDS application."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

_VALID_LOG_LEVELS = ("critical", "error", "warning", "info", "debug", "trace")


def build_parser() -> argparse.ArgumentParser:
    """Build the PHIDS command-line interface parser.

    Returns:
        argparse.ArgumentParser: Configured parser for launching the web UI/API server.
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
    """Launch the PHIDS FastAPI server.

    Args:
        argv: Optional command-line arguments, mainly for tests or embedding.
    """
    args = build_parser().parse_args(argv)

    import uvicorn

    uvicorn.run(
        "phids.api.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level,
    )


if __name__ == "__main__":
    main()

