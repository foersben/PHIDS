# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Command-line entry point for the PHIDS runtime server.

This module defines the process boundary between operating-system invocation and the PHIDS API runtime. It formalizes
host, port, reload, and logging controls so simulation services can be started reproducibly across local development
and containerized deployments. The launcher delegates execution to the FastAPI surface without mutating simulation
state, preserving deterministic behavior in downstream ECS and double-buffered engine phases.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Sequence  # noqa: TC003
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any

import typer

from phids.telemetry.export.core import aggregate_to_dataframe


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
    # Lazy import: heavy optional dependency kept off the startup path.
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
        # Lazy import: heavy optional dependency kept off the startup path.
        from phids.mcp import run_mcp_server

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
    # Lazy import: heavy optional dependency kept off the startup path.
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


class TelemetryExportFormat(StrEnum):
    """Supported telemetry export formats for headless batch runs."""

    NONE = "none"
    CSV = "csv"
    LATEX = "latex"
    BOTH = "both"


@dataclass(slots=True, frozen=True)
class _BatchExecutionConfig:
    """Validated parameter bundle for headless CLI batch execution."""

    scenario_path: Path
    runs: int
    max_ticks: int
    job_id: str
    label: str
    output_dir: Path
    seed_offset: int
    export_format: TelemetryExportFormat


@dataclass(slots=True, frozen=True)
class _ExportRequest:
    """Parameter bundle describing aggregate telemetry file export targets."""

    aggregate: dict[str, Any]
    export_format: TelemetryExportFormat
    output_dir: Path
    stem: str
    flora_names: dict[int, str]
    herbivore_names: dict[int, str]


def _load_validated_scenario(scenario_path: Path) -> tuple[dict[str, object], dict[int, str], dict[int, str]]:
    """Load, validate, and extract species metadata from a scenario JSON file."""
    # Lazy import: heavy optional dependency kept off the startup path.
    from pydantic import ValidationError

    from phids.api.schemas.simulation import SimulationConfig

    if not scenario_path.exists():
        typer.echo(f"Error: Scenario file '{scenario_path}' not found.", err=True)
        raise typer.Exit(code=1)

    try:
        raw_payload = json.loads(scenario_path.read_text(encoding="utf-8"))
        validated = SimulationConfig.model_validate(raw_payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        typer.echo(f"Error: Invalid scenario configuration '{scenario_path}': {exc}", err=True)
        raise typer.Exit(code=1) from exc

    flora_names = {sp.species_id: sp.name for sp in validated.flora_species}
    herbivore_names = {sp.species_id: sp.name for sp in validated.herbivore_species}
    scenario_dict: dict[str, object] = validated.model_dump(mode="json")
    return scenario_dict, flora_names, herbivore_names


def _write_batch_exports(req: _ExportRequest) -> list[Path]:
    """Export batch aggregate series as CSV and/or LaTeX booktabs tables."""
    if req.export_format == TelemetryExportFormat.NONE:
        return []

    df = aggregate_to_dataframe(
        req.aggregate,
        flora_names=req.flora_names or None,
        herbivore_names=req.herbivore_names or None,
    )
    if df.empty:
        return []

    req.output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    if req.export_format in (TelemetryExportFormat.CSV, TelemetryExportFormat.BOTH):
        csv_path = req.output_dir / f"{req.stem}.csv"
        csv_path.write_text(df.to_csv(index=False), encoding="utf-8")
        written.append(csv_path)
    if req.export_format in (TelemetryExportFormat.LATEX, TelemetryExportFormat.BOTH):
        tex_path = req.output_dir / f"{req.stem}_table.tex"
        tex_path.write_text(df.to_latex(index=False, float_format="%.2f"), encoding="utf-8")
        written.append(tex_path)
    return written


def _last_numeric(series: object, default: float = 0.0) -> float:
    """Return the final float element of a sequence, or ``default`` when empty."""
    if isinstance(series, list) and series:
        last = series[-1]
        if isinstance(last, (int, float)):
            return float(last)
    return default


def _format_batch_summary_lines(aggregate: dict[str, Any], job_id: str) -> list[str]:
    """Format concise human-readable telemetry summary lines for stdout."""
    ticks = aggregate.get("ticks", [])
    n_ticks = len(ticks) if isinstance(ticks, list) else 0
    runs_completed = aggregate.get("runs_completed", 0)
    ext_prob = float(aggregate.get("extinction_probability", 0.0))
    f_mean = _last_numeric(aggregate.get("flora_population_mean"))
    f_std = _last_numeric(aggregate.get("flora_population_std"))
    h_mean = _last_numeric(aggregate.get("herbivore_population_mean"))
    h_std = _last_numeric(aggregate.get("herbivore_population_std"))
    return [
        f"Job ID: {job_id} | Scenario: {aggregate.get('scenario_name', 'unnamed')}",
        f"Runs: {runs_completed} | Aligned ticks: {n_ticks} | Extinction P: {ext_prob:.4f}",
        f"Final flora population: {f_mean:.2f} +/- {f_std:.2f}",
        f"Final herbivore population: {h_mean:.2f} +/- {h_std:.2f}",
    ]


def _execute_batch_cli(cfg: _BatchExecutionConfig) -> None:
    """Run BatchRunner headlessly from a validated CLI configuration bundle."""
    # Lazy import: heavy optional dependency kept off the startup path.
    from phids.engine.batch.orchestrator import BatchRunner
    from phids.engine.batch.types import BatchExecutionRequest

    scenario_dict, flora_names, herbivore_names = _load_validated_scenario(cfg.scenario_path)
    resolved_label = cfg.label.strip() or cfg.scenario_path.stem
    runner = BatchRunner()
    result = runner.execute_batch(
        BatchExecutionRequest(
            scenario_dict=scenario_dict,
            runs=cfg.runs,
            max_ticks=cfg.max_ticks,
            job_id=cfg.job_id,
            output_dir=cfg.output_dir,
            scenario_name=resolved_label,
            seed_offset=cfg.seed_offset,
        )
    )
    aggregate = dict(result.aggregate)
    summary_path = cfg.output_dir / f"{cfg.job_id}_summary.json"
    for line in _format_batch_summary_lines(aggregate, cfg.job_id):
        typer.echo(line)
    typer.echo(f"Summary JSON: {summary_path}")

    written = _write_batch_exports(
        _ExportRequest(
            aggregate=aggregate,
            export_format=cfg.export_format,
            output_dir=cfg.output_dir,
            stem=cfg.job_id,
            flora_names=flora_names,
            herbivore_names=herbivore_names,
        )
    )
    for export_path in written:
        typer.echo(f"Exported: {export_path}")


def _resolve_summary_path(job_or_path: str, output_dir: Path) -> tuple[Path, str]:
    """Resolve a job identifier or explicit JSON file path to a summary JSON file."""
    candidate = Path(job_or_path)
    if candidate.exists() and candidate.is_file():
        stem = candidate.stem.removesuffix("_summary")
        return candidate, stem
    resolved = output_dir / f"{job_or_path}_summary.json"
    return resolved, job_or_path


@app.command()
def batch(
    scenario: Annotated[str, typer.Argument(help="Path to the validated SimulationConfig JSON file.")],
    runs: Annotated[int, typer.Option("--runs", "-r", min=1, max=256, help="Number of Monte Carlo runs.")] = 10,
    max_ticks: Annotated[int, typer.Option("--max-ticks", "-t", min=1, help="Maximum ticks per run.")] = 500,
    *,
    label: Annotated[str, typer.Option("--label", "-l", help="Optional scenario label for job summary.")] = "",
    output_dir: Annotated[str, typer.Option("--output-dir", "-o", help="Batch summary directory.")] = "data/batches",
    export_format: Annotated[
        TelemetryExportFormat,
        typer.Option("--export", "-e", help="Optional aggregate export format (none, csv, latex, both)."),
    ] = TelemetryExportFormat.NONE,
    seed_offset: Annotated[int, typer.Option("--seed-offset", min=0, help="Starting PRNG seed offset.")] = 0,
    job_id: Annotated[str, typer.Option("--job-id", help="Optional explicit job ID (auto-generated if empty).")] = "",
) -> None:
    """Execute headless Monte Carlo batch simulations and write UI-compatible summaries.

    Args:
        scenario: Path to the scenario JSON file.
        runs: Number of independent stochastic runs in ``[1, 256]``.
        max_ticks: Maximum simulation ticks per run.
        label: Optional scenario display label persisted into the summary JSON.
        output_dir: Directory where ``{job_id}_summary.json`` and exports are saved.
        export_format: Aggregate telemetry export format.
        seed_offset: Initial PRNG seed offset for reproducible ensembles.
        job_id: Optional explicit batch job identifier.
    """
    cfg = _BatchExecutionConfig(
        scenario_path=Path(scenario),
        runs=runs,
        max_ticks=max_ticks,
        job_id=job_id.strip() or uuid.uuid4().hex[:8],
        label=label,
        output_dir=Path(output_dir),
        seed_offset=seed_offset,
        export_format=export_format,
    )
    _execute_batch_cli(cfg)


@app.command("batch-inspect")
def batch_inspect(
    job_or_path: Annotated[str, typer.Argument(help="Batch job_id or direct path to a *_summary.json file.")],
    *,
    output_dir: Annotated[str, typer.Option("--output-dir", "-o", help="Batch summary directory.")] = "data/batches",
    export_format: Annotated[
        TelemetryExportFormat,
        typer.Option("--export", "-e", help="Optional aggregate export format (none, csv, latex, both)."),
    ] = TelemetryExportFormat.NONE,
    scenario: Annotated[str, typer.Option("--scenario", "-s", help="Optional scenario JSON for species names.")] = "",
    export_dir: Annotated[str, typer.Option("--export-dir", help="Directory for exported telemetry files.")] = "",
) -> None:
    """Inspect a completed batch summary JSON and optionally export CSV/LaTeX telemetry.

    Args:
        job_or_path: Batch job identifier or path to a ``*_summary.json`` file.
        output_dir: Directory searched when ``job_or_path`` is a job identifier.
        export_format: Optional telemetry export format.
        scenario: Optional scenario JSON path to label species columns cleanly.
        export_dir: Optional directory for CSV/LaTeX exports (defaults to summary directory).
    """
    summary_path, resolved_job_id = _resolve_summary_path(job_or_path, Path(output_dir))
    if not summary_path.exists():
        typer.echo(f"Error: Batch summary '{summary_path}' not found.", err=True)
        raise typer.Exit(code=1)

    aggregate = dict(json.loads(summary_path.read_text(encoding="utf-8")))
    flora_names: dict[int, str] = {}
    herbivore_names: dict[int, str] = {}
    if scenario.strip():
        _, flora_names, herbivore_names = _load_validated_scenario(Path(scenario))

    for line in _format_batch_summary_lines(aggregate, resolved_job_id):
        typer.echo(line)

    target_dir = Path(export_dir) if export_dir.strip() else summary_path.parent
    written = _write_batch_exports(
        _ExportRequest(
            aggregate=aggregate,
            export_format=export_format,
            output_dir=target_dir,
            stem=resolved_job_id,
            flora_names=flora_names,
            herbivore_names=herbivore_names,
        )
    )
    for export_path in written:
        typer.echo(f"Exported: {export_path}")


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
