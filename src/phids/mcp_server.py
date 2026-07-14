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

import dataclasses
import json
import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from mcp.server.fastmcp import FastMCP

from phids.api.ui_state import get_draft
from phids.shared.logging_config import get_recent_logs

if TYPE_CHECKING:
    from phids.api.ui_state import DraftState

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
        draft: The active :class:`~phids.api.ui_state.DraftState` instance.

    Returns:
        Indented JSON string suitable for agent consumption.

    """

    def _default(obj: object) -> Any:
        if hasattr(obj, "model_dump"):
            return cast("Any", obj).model_dump()
        # Nested stdlib dataclasses that slipped past dataclasses.asdict recursion
        if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
            return dataclasses.asdict(obj)
        raise TypeError(f"Type {type(obj).__name__} is not JSON serializable")

    return json.dumps(dataclasses.asdict(draft), indent=2, default=_default)


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
        Indented JSON string of the current :class:`~phids.api.ui_state.DraftState`.

    """
    return _draft_to_json(get_draft())


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
        "flora_species_count": len(draft.flora_species),
        "herbivore_species_count": len(draft.herbivore_species),
        "substance_definitions_count": len(draft.substance_definitions),
        "trigger_rules_count": len(draft.trigger_rules),
        "initial_plants_count": len(draft.initial_plants),
        "initial_swarms_count": len(draft.initial_swarms),
        "termination_thresholds": {
            "z2_flora_species_extinction": draft.z2_flora_species_extinction,
            "z4_herbivore_species_extinction": draft.z4_herbivore_species_extinction,
            "z6_max_total_flora_energy": draft.z6_max_total_flora_energy,
            "z7_max_total_herbivore_population": draft.z7_max_total_herbivore_population,
        },
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
