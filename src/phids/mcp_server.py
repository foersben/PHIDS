# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Model Context Protocol surface for autonomous PHIDS orchestration.

Exposes read-only simulation states as structural resources and provides
agentic tools for system validation and telemetry inspection without violating
the engine's single-writer architecture.

Architecture overview
---------------------
- **Resources** - Declarative, passively-read context feeds that consuming
  agents can cache and reference without spending a tool-call budget.
- **Tools** - Targeted execution primitives for read-only inspection,
  validation, and diagnostics.
- **Prompts** - Pre-baked guidance fragments that wire the above surfaces
  into coherent agentic workflows.

The MCP server runs as a headless stdio process completely decoupled from the
FastAPI HTTP layer.  It may be launched independently via ``just mcp`` or
programmatically via :func:`run_mcp_server`.  No write paths into the engine
state are exposed.
"""

from __future__ import annotations

import base64
import dataclasses
import json
import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from mcp.server.fastmcp import FastMCP
from pydantic import ValidationError

from phids.api.schemas.simulation import SimulationConfig
from phids.api.ui_state.state import get_draft
from phids.shared.logging_config import get_recent_logs

if TYPE_CHECKING:
    from phids.api.ui_state.state import DraftState

# Resolved at import time so subprocess calls can locate scripts/ reliably
# regardless of the working directory set by the calling process.
# Layout: src/phids/mcp_server.py  ->  parents[0]=src/phids, [1]=src, [2]=PHIDS/
_PROJECT_ROOT: Path = Path(__file__).parents[2]

mcp = FastMCP(
    "PHIDS-Orchestrator",
    instructions=(
        "Read-only MCP surface for the PHIDS plant-herbivore simulation engine. "
        "Use the phids://config/draft.json resource for passive context reads before "
        "invoking tools. Tools are scoped to inspection and validation only - never "
        "attempt to mutate engine state through this interface."
    ),
)


@mcp.tool()
def query_batch_jobs() -> dict[str, Any]:
    """Return a summary of active and completed batch jobs from the draft state.

    Provides visibility into long-running exploration tasks or evolutionary
    exploration results.

    Returns:
        dict[str, Any]: Dictionary mapping job IDs to their state representations.
    """
    draft = get_draft()
    return {
        job_id: {
            "status": state.status,
            "completed_runs": state.completed,
            "total_runs": state.total,
            "finished_at": state.finished_at,
        }
        for job_id, state in draft.active_batch_jobs.items()
    }


# ===========================================================================
# Internal helpers
# ===========================================================================


def _draft_to_json(draft: DraftState) -> str:
    """Serialize a mixed dataclass/Pydantic DraftState tree to JSON.

    ``DraftState`` is a stdlib dataclass whose list fields contain a mix of
    further stdlib dataclasses (``TriggerRule``, ``PlacedPlant``, ...) and Pydantic
    models (``FloraSpeciesParams``, ``HerbivoreSpeciesParams``, ``BatchJobState``).
    ``dataclasses.asdict`` handles the dataclass hierarchy but copies Pydantic
    models verbatim; the ``_default`` hook converts those during JSON encoding.

    Args:
        draft: The active :class:`~phids.api.ui_state.state.DraftState` instance.

    Returns:
        Indented JSON string suitable for agent consumption.
    """

    def _default(obj: object) -> Any:
        """Convert non-serializable objects to JSON serializable format.

        Args:
            obj: Object to convert.

        Raises:
            TypeError: Object is not JSON serializable.

        Returns:
            JSON serializable representation of the object.
        """
        if hasattr(obj, "model_dump"):
            return cast("Any", obj).model_dump()
        # Nested stdlib dataclasses that slipped past dataclasses.asdict recursion
        if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
            return dataclasses.asdict(obj)
        raise TypeError(f"Type {type(obj).__name__} is not JSON serializable")

    return json.dumps(dataclasses.asdict(draft), indent=2, default=_default)


def _get_active_sim_loop() -> Any | None:
    """Safely return the active live SimulationLoop instance if loaded under FastAPI."""
    try:
        from phids.api import main as api_main

        return getattr(api_main, "_sim_loop", None)
    except (ImportError, AttributeError):
        return None


# ===========================================================================
# 1. RESOURCES - declarative context data feeds
# ===========================================================================


@mcp.resource("phids://config/draft.json")
def active_draft_resource() -> str:
    """Provide the full, untruncated JSON layout of the active configuration draft.

    Agents can read this resource directly to digest species mappings, substance
    definitions, trigger-rule trees, diet matrices, and termination thresholds
    without spending a tool-call budget on ``runtime_snapshot``.

    Returns:
        Indented JSON string of the current :class:`~phids.api.ui_state.state.DraftState`.

    """
    return _draft_to_json(get_draft())


@mcp.resource("phids://simulation/live.json")
def live_simulation_resource() -> str:
    """Provide real-time JSON snapshot of the active running SimulationLoop.

    Returns live tick count, status flags, active ECS entity counts, total plant
    energy, total herbivore population, and mycorrhizal connection stats.

    Returns:
        Indented JSON string of the live simulation loop status.
    """
    loop = _get_active_sim_loop()
    if loop is None:
        return json.dumps({"status": "idle", "message": "No active simulation loop currently loaded"})

    from phids.engine.components.plant import PlantComponent
    from phids.engine.components.swarm import SwarmComponent

    plants = [e.get_component(PlantComponent) for e in loop.world.query(PlantComponent)]
    swarms = [e.get_component(SwarmComponent) for e in loop.world.query(SwarmComponent)]

    total_links = sum(len(p.mycorrhizal_connections) for p in plants) // 2

    return json.dumps(
        {
            "status": "running" if loop.running and not loop.paused else ("paused" if loop.paused else "ready"),
            "tick": loop.tick,
            "max_ticks": loop.config.max_ticks,
            "terminated": loop.terminated,
            "termination_reason": loop.termination_reason,
            "active_plants": len(plants),
            "active_swarms": len(swarms),
            "total_flora_energy": round(sum(p.energy for p in plants), 2),
            "total_herbivore_population": sum(s.population for s in swarms),
            "mycorrhizal_links_count": total_links,
        },
        indent=2,
    )


# ===========================================================================
# 2. TOOLS - actionable inspection primitives
# ===========================================================================


@mcp.tool()
def runtime_snapshot() -> dict[str, Any]:
    """Return a compact performance-and-counts summary of the active draft state.

    Useful as a lightweight sanity check before heavier resource reads or batch
    operations.  All counts reflect the in-memory singleton draft; no simulation
    loop is touched.

    Returns:
        dict[str, Any]: Compact read-only summary including scenario metadata,
        grid dimensions, entity counts, and active termination thresholds
        (Z-codes).
    """
    draft = get_draft()
    return {
        "scenario_name": draft.scenario_name,
        "dimensions": f"{draft.grid_width}x{draft.grid_height}",
        "grid_width": draft.grid_width,
        "grid_height": draft.grid_height,
        "max_ticks": draft.max_ticks,
        "tick_rate_hz": draft.tick_rate_hz,
        "placement_mode": draft.placement_mode,
        "mycorrhizal_inter_species": draft.mycorrhizal_inter_species,
        "flora_species_count": len(draft.flora_species),
        "herbivore_species_count": len(draft.herbivore_species),
        "substance_definitions_count": len(draft.substance_definitions),
        "trigger_rules_count": len(draft.trigger_rules),
        "initial_plants_count": len(draft.initial_plants),
        "initial_swarms_count": len(draft.initial_swarms),
        "active_batch_jobs_count": len(draft.active_batch_jobs),
        "termination_thresholds": {
            "z2_flora_species_extinction": draft.z2_flora_species_extinction,
            "z4_herbivore_species_extinction": draft.z4_herbivore_species_extinction,
            "z6_max_total_flora_energy": draft.z6_max_total_flora_energy,
            "z7_max_total_herbivore_population": draft.z7_max_total_herbivore_population,
        },
    }


@mcp.tool()
def inspect_live_simulation() -> dict[str, Any]:
    """Return compact operational summary of the active running simulation loop.

    Useful for monitoring tick advancement, modulo-stride gates (is_medium_tick,
    is_slow_tick), and mycorrhizal root network connectivity statistics.

    Returns:
        dict[str, Any]: Compact operational breakdown of the live running loop.
    """
    loop = _get_active_sim_loop()
    if loop is None:
        return {"status": "inactive", "message": "No live simulation loop currently loaded"}

    from phids.engine.components.plant import PlantComponent
    from phids.engine.components.swarm import SwarmComponent

    plants = [e.get_component(PlantComponent) for e in loop.world.query(PlantComponent)]
    swarms = [e.get_component(SwarmComponent) for e in loop.world.query(SwarmComponent)]

    connected_plants = sum(1 for p in plants if p.mycorrhizal_connections)
    total_links = sum(len(p.mycorrhizal_connections) for p in plants) // 2

    return {
        "status": "active",
        "tick": loop.tick,
        "is_medium_tick": loop.tick % 24 == 0,
        "is_slow_tick": loop.tick % 168 == 0,
        "running": loop.running,
        "paused": loop.paused,
        "terminated": loop.terminated,
        "termination_reason": loop.termination_reason,
        "plant_count": len(plants),
        "swarm_count": len(swarms),
        "total_flora_energy": round(sum(p.energy for p in plants), 2),
        "total_herbivore_population": sum(s.population for s in swarms),
        "mycorrhizal_total_links": total_links,
        "mycorrhizal_connected_plants": connected_plants,
    }


def _validate_plant_invariants(plants: list[Any], active_eids: set[int], violations: list[str]) -> None:
    """Validate invariants for all active plants."""
    for p in plants:
        if p.energy < 0.0:
            violations.append(f"Plant {p.entity_id} has negative energy: {p.energy}")
        elif 0.0 < p.energy < 1e-12:
            violations.append(f"Plant {p.entity_id} has subnormal float energy: {p.energy}")

        for target_eid in p.mycorrhizal_connections:
            if target_eid not in active_eids:
                violations.append(f"Plant {p.entity_id} holds dead mycorrhizal reference to entity {target_eid}")


def _validate_swarm_invariants(swarms: list[Any], violations: list[str]) -> None:
    """Validate invariants for all active swarms."""
    for s in swarms:
        if s.energy < 0.0:
            violations.append(f"Swarm {s.entity_id} has negative energy: {s.energy}")
        if s.population <= 0:
            violations.append(f"Swarm {s.entity_id} has zero or negative population: {s.population}")


@mcp.tool()
def validate_biological_invariants() -> dict[str, Any]:
    """Audit the running simulation against spatiotemporal biological mandates.

    Checks for:
    1. Orphaned mycorrhizal references to dead/culled entities.
    2. Subnormal float energy levels (< 1e-12) indicative of FPU traps.
    3. Negative plant or swarm energy values.

    Returns:
        dict[str, Any]: Verification status, violation count, and list of error details.
    """
    loop = _get_active_sim_loop()
    if loop is None:
        return {"status": "error", "message": "Simulation loop must be active to validate invariants"}

    from phids.engine.components.plant import PlantComponent
    from phids.engine.components.swarm import SwarmComponent

    violations: list[str] = []
    plants = [e.get_component(PlantComponent) for e in loop.world.query(PlantComponent)]
    swarms = [e.get_component(SwarmComponent) for e in loop.world.query(SwarmComponent)]
    active_eids = set(loop.world._entities.keys())

    _validate_plant_invariants(plants, active_eids, violations)
    _validate_swarm_invariants(swarms, violations)

    return {
        "compliant": len(violations) == 0,
        "violations_count": len(violations),
        "violations": violations,
    }


@mcp.tool()
def inspect_telemetry_schema(zarr_store_path: str) -> dict[str, Any]:
    """Expose Zarr replay store structure to the agent without loading field arrays.

    Allows autonomous MLOps operators to inspect frame counts, top-level tree
    keys, and store-level metadata before initiating a heavy Polars lazy-frame
    extraction.  The store is opened read-only; no data is mutated.

    Args:
        zarr_store_path: Filesystem path to a PHIDS ``.zarr`` replay store
            directory.

    Returns:
        dict[str, Any]: On success - ``status``, ``store_path``, ``frame_count``,
        ``tree_keys``, and ``store_attrs``.  On failure - ``status`` and
        ``message``.
    """
    try:
        import numpy as np
        import zarr
    except ImportError as exc:  # pragma: no cover
        return {"status": "error", "message": f"Required package not available: {exc}"}

    store = Path(zarr_store_path)
    if not store.exists():
        return {
            "status": "error",
            "message": f"Store path does not exist: {zarr_store_path}",
        }

    try:
        root: zarr.Group = zarr.open_group(str(store), mode="r")
        tree_keys: list[str] = list(root.keys())

        # Derive frame count from the consolidated _metadata JSON array.
        frame_count: int = 0
        if "_metadata" in root:
            try:
                meta_node = cast("zarr.Array[Any]", root["_metadata"])
                meta_bytes = bytes(np.asarray(meta_node[:], dtype=np.uint8).tolist())
                meta_obj = json.loads(meta_bytes.decode("utf-8"))
                if isinstance(meta_obj, list):
                    frame_count = len(meta_obj)
                elif isinstance(meta_obj, dict) and "_metadata" in meta_obj:
                    inner = meta_obj["_metadata"]
                    frame_count = len(inner) if isinstance(inner, list) else 0
            except Exception:  # pragma: no cover - corrupt metadata
                frame_count = -1  # Corrupt metadata - indicate uncertainty

        store_attrs: dict[str, Any] = dict(root.attrs) if root.attrs else {}

        return {
            "status": "success",
            "store_path": str(store.resolve()),
            "frame_count": frame_count,
            "tree_keys": tree_keys,
            "store_attrs": store_attrs,
        }
    except Exception as exc:
        return {"status": "error", "message": f"Failed to read Zarr store: {exc}"}


@mcp.tool()
def validate_okf_compliance() -> dict[str, Any]:
    """Run the OKF knowledge-graph validation suite against the docs/ and .agents/ trees.

    Invokes ``scripts/validate_okf.py`` via ``uv run`` from the project root,
    mirroring the pre-commit hook execution environment exactly.  Essential for
    self-evolving agent loops to verify that documentation mutations remain
    structurally valid before opening a PR.

    Returns:
        dict[str, Any]: ``compliant`` (bool), ``violations`` (list of extracted
        error lines), and ``output`` (full captured stdout+stderr).
    """
    uv_bin = shutil.which("uv") or "uv"

    try:
        result = subprocess.run(
            [uv_bin, "run", "python", "scripts/validate_okf.py"],
            cwd=_PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError:
        return {
            "compliant": False,
            "violations": [f"Executable not found: {uv_bin}"],
            "output": "",
        }
    except subprocess.TimeoutExpired:
        return {
            "compliant": False,
            "violations": ["Validation process timed out after 30 s"],
            "output": "",
        }

    compliant: bool = result.returncode == 0
    combined: str = (result.stdout + result.stderr).strip()
    # Extract individual violation lines (lines containing the bullet marker).
    violations: list[str] = [
        line.strip().lstrip("\u2022").strip() for line in combined.splitlines() if "\u2022" in line or "\u274c" in line
    ]
    return {
        "compliant": compliant,
        "violations": violations,
        "output": combined,
    }


@mcp.tool()
def query_diagnostic_logs(limit: int = 80) -> list[dict[str, str]]:
    """Return the newest structured diagnostic entries recorded by PHIDS.

    Entries are emitted by all engine, API, and telemetry loggers via the
    :class:`~phids.shared.logging_config.InMemoryLogHandler` ring buffer.
    Ordered most-recent-first.

    Args:
        limit: Maximum number of log rows to return (clamped to >= 1 internally).

    Returns:
        list[dict[str, str]]: Structured entries with ``timestamp``, ``level``,
        ``logger``, ``module``, and ``message`` keys.
    """
    return get_recent_logs(limit=limit)


# ===========================================================================
# 3. PROMPTS - pre-baked agent guidance
# ===========================================================================


@mcp.tool()
def validate_simulation_config(config_json: str) -> dict[str, Any]:
    """Validate a JSON string against the strict PHIDS SimulationConfig schema.

    Allows autonomous agents to verify that AI-generated configuration files
    comply with all engine requirements (e.g., power-of-two grid bounds,
    matching species IDs) before attempting to launch a simulation.

    Args:
        config_json: The JSON string payload to validate.

    Returns:
        dict[str, Any]: A dictionary with a ``valid`` boolean and a ``errors`` list.
    """
    try:
        SimulationConfig.model_validate_json(config_json)
        return {"valid": True, "errors": []}
    except ValidationError as e:
        return {"valid": False, "errors": [str(err["msg"]) for err in e.errors()]}
    except Exception as e:
        return {"valid": False, "errors": [str(e)]}


@mcp.tool()
def query_telemetry_schema() -> dict[str, Any]:
    """Return the available telemetry metrics for the active simulation.

    Agents can use this to determine which data columns are available to plot or export
    using the export_telemetry_data tool.

    Returns:
        dict[str, Any]: Available columns and structural layout.
    """
    loop = _get_active_sim_loop()
    if loop is None:
        return {"status": "error", "message": "No active simulation loop loaded."}

    try:
        # Check if any telemetry is recorded
        rows = loop.telemetry._rows
        if not rows:
            return {"status": "success", "columns": [], "message": "No telemetry recorded yet."}

        columns = list(rows[0].keys())
        return {"status": "success", "columns": columns}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def _generate_export(
    format: str,
    normalized_data_type: str,
    rows: list[dict[str, Any]],
    filtered_rows: list[dict[str, Any]],
    flora_names: dict[int, str],
    herbivore_names: dict[int, str],
    plant_species_id: int,
    herbivore_species_id: int,
    tick_interval: int,
    columns: str | None,
    flora_ids: str | None,
    herbivore_ids: str | None,
    title: str | None,
    x_label: str | None,
    y_label: str | None,
    x_max: float | None,
    y_max: float | None,
) -> dict[str, Any]:
    """Helper function to generate telemetry export."""
    if format == "csv":
        from phids.telemetry.export.core import (
            aggregate_to_dataframe,
            decimate_dataframe,
            filter_dataframe_columns,
            telemetry_to_dataframe,
        )

        if normalized_data_type in ("timeseries", "defense_economy", "biomass_stack"):
            df = aggregate_to_dataframe(filtered_rows)  # type: ignore
        else:
            df = telemetry_to_dataframe(filtered_rows)

        if tick_interval > 1:
            df = decimate_dataframe(df, tick_interval)

        if columns:
            df = filter_dataframe_columns(df, columns)

        bytes_data = df.to_csv(index=False).encode("utf-8")
        return {"status": "success", "format": format, "data": bytes_data.decode("utf-8")}

    elif format == "tex_table":
        from phids.telemetry.export.latex import export_bytes_tex_table

        bytes_data = export_bytes_tex_table(
            rows,
            columns=columns,
            include_flora_ids=flora_ids,
            include_herbivore_ids=herbivore_ids,
            tick_interval=tick_interval,
        )
        return {"status": "success", "format": format, "data": bytes_data.decode("utf-8")}

    elif format == "tex_tikz":
        from phids.telemetry.export.tikz import generate_tikz_str

        tikz_str = generate_tikz_str(
            filtered_rows,
            normalized_data_type,
            flora_names=flora_names,
            herbivore_names=herbivore_names,
            plant_species_id=plant_species_id,
            herbivore_species_id=herbivore_species_id,
            include_flora_ids=flora_ids,
            include_herbivore_ids=herbivore_ids,
            title=title,
            x_label=x_label,
            y_label=y_label,
            x_max=x_max,
            y_max=y_max,
        )
        return {"status": "success", "format": format, "data": tikz_str}

    elif format == "png":
        from phids.telemetry.export.png import generate_png_bytes

        bytes_data = generate_png_bytes(
            filtered_rows,
            normalized_data_type,
            flora_names=flora_names,
            herbivore_names=herbivore_names,
            plant_species_id=plant_species_id,
            herbivore_species_id=herbivore_species_id,
            include_flora_ids=flora_ids,
            include_herbivore_ids=herbivore_ids,
            title=title,
            x_label=x_label,
            y_label=y_label,
            x_max=x_max,
            y_max=y_max,
        )
        return {"status": "success", "format": format, "data": base64.b64encode(bytes_data).decode("utf-8")}

    return {"status": "error", "message": "Unknown format"}


@mcp.tool()
def export_telemetry_data(
    format: str,
    data_type: str = "timeseries",
    tick_interval: int = 1,
    plant_species_id: int = 0,
    herbivore_species_id: int = 0,
    columns: str | None = None,
    flora_ids: str | None = None,
    herbivore_ids: str | None = None,
    title: str | None = None,
    x_label: str | None = None,
    y_label: str | None = None,
    x_max: float | None = None,
    y_max: float | None = None,
) -> dict[str, Any]:
    """Export telemetry from the active simulation as an encoded string.

    Generates academic telemetry exports (CSV, PNG, TikZ, LaTeX) mirroring
    the FastAPI endpoints but returning the payload directly for agent consumption.

    Args:
        format: 'csv', 'tex_table', 'tex_tikz', or 'png'.
        data_type: 'timeseries', 'phasespace', 'defense_economy', 'biomass_stack', 'metabolic'.
        tick_interval: Decimation factor for large datasets (e.g. 10 = every 10th tick).
        plant_species_id: Flora species ID for phase-space axes.
        herbivore_species_id: Herbivore species ID for phase-space axes.
        columns: Comma-separated list of columns to include.
        flora_ids: Comma-separated list of flora species to include.
        herbivore_ids: Comma-separated list of herbivore species to include.
        title: Chart title override.
        x_label: X-axis label override.
        y_label: Y-axis label override.
        x_max: X-axis scale maximum.
        y_max: Y-axis scale maximum.

    Returns:
        dict[str, Any]: A dictionary containing ``status``, ``format``, and ``data``.
        For binary formats (png), ``data`` is a base64 encoded string.
        For text formats (csv, tex_table, tex_tikz), ``data`` is a UTF-8 string.
    """
    loop = _get_active_sim_loop()
    if loop is None:
        return {"status": "error", "message": "No active simulation loop loaded."}

    normalized_data_type = "defense_economy" if data_type == "metabolic" else data_type
    valid_data_types = {"timeseries", "phasespace", "defense_economy", "biomass_stack"}

    if normalized_data_type not in valid_data_types:
        return {"status": "error", "message": f"Invalid data_type. Must be one of {valid_data_types}"}

    if format not in {"csv", "tex_table", "tex_tikz", "png"}:
        return {"status": "error", "message": "Invalid format. Must be csv, tex_table, tex_tikz, or png."}

    try:
        from phids.telemetry.export.core import filter_telemetry_rows

        rows = loop.telemetry._rows
        flora_names = {sp.species_id: sp.name for sp in loop.config.flora_species}
        herbivore_names = {sp.species_id: sp.name for sp in loop.config.herbivore_species}

        filtered_rows = filter_telemetry_rows(rows, flora_ids=flora_ids, herbivore_ids=herbivore_ids)

        return _generate_export(
            format,
            normalized_data_type,
            rows,
            filtered_rows,
            flora_names,
            herbivore_names,
            plant_species_id,
            herbivore_species_id,
            tick_interval,
            columns,
            flora_ids,
            herbivore_ids,
            title,
            x_label,
            y_label,
            x_max,
            y_max,
        )

    except Exception as e:
        return {"status": "error", "message": f"Export generation failed: {e}"}
    return {"status": "error", "message": "Unknown format"}


@mcp.tool()
def read_batch_summary(job_id: str) -> dict[str, Any]:
    """Read the aggregated metrics inside a batch job's summary JSON file.

    Allows agents to digest batch job metric summaries without manually
    loading JSON artifacts.

    Args:
        job_id: The ID of the batch job to read.

    Returns:
        dict[str, Any]: Dictionary containing the aggregated metrics on success,
        or an error message on failure.
    """
    summary_path = _PROJECT_ROOT / "data" / "batches" / f"{job_id}_summary.json"
    if not summary_path.exists():
        return {"status": "error", "message": f"Summary file not found: {summary_path}"}

    try:
        with open(summary_path, encoding="utf-8") as f:
            return {"status": "success", "data": json.load(f)}
    except Exception as exc:
        return {"status": "error", "message": f"Failed to read summary file: {exc}"}


@mcp.prompt()
def analyze_simulation_drift() -> str:
    """Pre-configured prompt mapping to guide debugging agents through drift triage.

    Returns:
        str: Structured step-by-step investigation guide for stochastic drift
        anomalies inside the PHIDS engine.

    """
    return (
        "You are tasked with evaluating a stochastic drift anomaly inside the PHIDS engine.\n\n"
        "Follow this triage protocol in order:\n"
        "1. Read `phids://config/draft.json` to establish full scenario context "
        "(species, substances, termination thresholds).\n"
        "2. Call `runtime_snapshot` to confirm active entity counts and Z-code thresholds "
        "match your expectations.\n"
        "3. Call `query_diagnostic_logs` (limit=120) and scan for WARNING/ERROR entries "
        "from `phids.engine.loop`, `phids.engine.systems.*`, or Numba compilation traces.\n"
        "4. Call `validate_okf_compliance` to verify no documentation invariants were "
        "silently broken by a recent schema mutation.\n"
        "5. If a Zarr replay buffer path is available, call `inspect_telemetry_schema` "
        "to confirm frame counts and field arrays are structurally intact.\n"
        "6. Cross-reference all findings. Propose concrete parameter remediation steps "
        "targeting the most probable root cause (seed entropy, flow-field boundary, "
        "or trigger-rule population threshold)."
    )


# ===========================================================================
# Entry point
# ===========================================================================


def run_mcp_server() -> None:
    """Spawn the headless stdio MCP communications loop."""
    mcp.run()


if __name__ == "__main__":
    run_mcp_server()
