# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Command-line entry point for the PHIDS runtime server.

This module defines the process boundary between operating-system invocation and the PHIDS API runtime. It formalizes
host, port, reload, and logging controls so simulation services can be started reproducibly across local development
and containerized deployments. The launcher delegates execution to the FastAPI surface without mutating simulation
state, preserving deterministic behavior in downstream ECS and double-buffered engine phases.
"""

from __future__ import annotations

from collections.abc import Sequence  # noqa: TC003
from enum import StrEnum
from typing import Annotated

import typer


class LogLevel(StrEnum):
    """Enumerate supported Uvicorn log levels for CLI validation."""

    CRITICAL = "critical"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    DEBUG = "debug"
    TRACE = "trace"


app = typer.Typer(
    add_completion=True,
    invoke_without_command=True,
    help=("Run the PHIDS FastAPI server that powers the JSON API, HTMX UI, and WebSocket simulation streams."),
)


def _run_server(*, host: str, port: int, reload: bool, log_level: str) -> None:
    """Launch Uvicorn with a deterministic PHIDS application configuration.

    This function provides an isolated execution boundary between command parsing and process startup. Isolating this
    call preserves testability while maintaining a strict mapping from validated CLI parameters to the ASGI
    runtime surface.

    Args:
        host: Interface address for HTTP binding.
        port: TCP port for HTTP binding.
        reload: Auto-reload flag for local development.
        log_level: Uvicorn logging verbosity.

    """
    import uvicorn

    uvicorn.run(
        "phids.api.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level=log_level,
    )


@app.callback(invoke_without_command=True)
def serve(
    ctx: typer.Context,
    host: Annotated[
        str,
        typer.Option(help="Interface to bind the HTTP server to. Use 0.0.0.0 inside containers."),
    ] = "127.0.0.1",
    port: Annotated[int, typer.Option(help="TCP port for the FastAPI server.")] = 8000,
    reload: Annotated[bool, typer.Option(help="Enable auto-reload for local development.")] = False,
    log_level: Annotated[LogLevel, typer.Option(help="Uvicorn log verbosity.")] = LogLevel.INFO,
    mcp: Annotated[
        bool,
        typer.Option(help="Start the PHIDS stdio MCP server instead of the HTTP runtime."),
    ] = False,
) -> None:
    """Start the PHIDS FastAPI application from validated CLI options.

    The callback defines a typed command surface that is validated before server startup. Keeping this mapping
    explicit ensures that network exposure and observability controls remain reproducible across local,
    containerized, and CI-managed runtime contexts.

    Args:
        ctx: Typer context containing invoked subcommands.
        host: Interface address for HTTP binding.
        port: TCP port for HTTP binding.
        reload: Auto-reload flag for local development.
        log_level: Uvicorn logging verbosity.
        mcp: Whether to start the MCP stdio server instead of Uvicorn.

    """
    if ctx.invoked_subcommand is not None:
        return

    if mcp:
        from phids.mcp_server import run_mcp_server

        run_mcp_server()
        return

    _run_server(host=host, port=port, reload=reload, log_level=log_level.value)


@app.command()
def tune(
    blueprint_path: Annotated[
        str,
        typer.Argument(help="Path to the baseline scenario JSON blueprint."),
    ],
    grid_size: Annotated[int, typer.Option(help="Grid size for optimization runs (must be squared).")] = 80,
    ticks: Annotated[int, typer.Option(help="Target simulation ticks per run.")] = 2500,
    samples: Annotated[int, typer.Option(help="Number of concurrent simulation samples per evaluation.")] = 20,
    out: Annotated[
        str, typer.Option(help="Output path for the winning configuration JSON.")
    ] = "examples/eternal_canopy.json",
) -> None:
    """Run the native PHIDS hyperparameter tuning pipeline to find a stable configuration.

    Args:
        blueprint_path: The file path to the scenario configuration blueprint to use as a baseline.
        budget: The maximum execution time allowed for the tuning optimization search.
        grid_size: The spatial dimensions (width and height) for the simulation environment during tuning.
        mode: The tuning optimization strategy or mode to apply (e.g. 'bayesian', 'random').
        out: The directory path where the tuning results and optimal configuration should be saved.
        samples: The number of distinct configuration candidates to sample during optimization.
        ticks: The number of simulation steps (ticks) to run each candidate evaluation.
    """
    import json
    from pathlib import Path

    from phids.analytics.tuning import TrophicOptimizer

    path = Path(blueprint_path)
    if not path.exists():
        typer.echo(f"Error: Blueprint file '{path}' not found.", err=True)
        raise typer.Exit(code=1)

    with path.open("r", encoding="utf-8") as fp:
        blueprint = json.load(fp)

    # Ensure grid size is clamped to user request
    blueprint["grid_width"] = grid_size
    blueprint["grid_height"] = grid_size

    typer.echo(f"Initializing tuning pipeline with target {ticks} ticks and {samples} samples per evaluation...")
    optimizer = TrophicOptimizer(blueprint=blueprint, runs_per_eval=samples, max_ticks=ticks)
    best_config = optimizer.optimize()

    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fp:
        json.dump(best_config, fp, indent=2)

    typer.echo(f"Success! Optimized configuration written to {out_path.absolute()}")


def main(argv: Sequence[str] | None = None) -> None:
    """Start the PHIDS FastAPI application with parsed runtime arguments.

    This function materializes command-line intent into a concrete ASGI server configuration. It resolves
    arguments, loads the API application, and transfers control to Uvicorn for long-running service orchestration.

    Args:
        argv: Optional argument sequence used by tests or embedding contexts.

    Returns:
        None. The function starts the server process and does not produce a data value.

    """
    app(
        args=list(argv) if argv is not None else None,
        prog_name="phids",
        standalone_mode=False,
    )


if __name__ == "__main__":
    main()
