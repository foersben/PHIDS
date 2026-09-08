# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Biological, schema, and knowledge invariants validation tools for FastMCP."""

from __future__ import annotations

import shutil
import subprocess
from typing import Any

from pydantic import ValidationError

from phids.api.schemas.simulation import SimulationConfig
from phids.mcp.app import mcp
from phids.mcp.helpers import get_active_sim_loop, get_logs, get_project_root, run_subprocess


def _validate_plant_invariants(plants: list[Any], active_eids: set[int], violations: list[str]) -> None:
    """Validate invariants for all active plants.

    Args:
        plants: List of active plant components.
        active_eids: Set of entity IDs currently registered in the ECS world.
        violations: Output list collecting encountered violation messages.
    """
    for p in plants:
        if p.energy < 0.0:
            violations.append(f"Plant {p.entity_id} has negative energy: {p.energy}")
        elif 0.0 < p.energy < 1e-12:
            violations.append(f"Plant {p.entity_id} has subnormal float energy: {p.energy}")

        for target_eid in p.mycorrhizal_connections:
            if target_eid not in active_eids:
                violations.append(f"Plant {p.entity_id} holds dead mycorrhizal reference to entity {target_eid}")


def _validate_swarm_invariants(swarms: list[Any], violations: list[str]) -> None:
    """Validate invariants for all active swarms.

    Args:
        swarms: List of active swarm components.
        violations: Output list collecting encountered violation messages.
    """
    for s in swarms:
        if s.energy < 0.0:
            violations.append(f"Swarm {s.entity_id} has negative energy: {s.energy}")
        if s.population <= 0:
            violations.append(f"Swarm {s.entity_id} has zero or negative population: {s.population}")


@mcp.tool()
def validate_simulation_config(config_json: str) -> dict[str, Any]:
    """Validate a JSON string against the strict PHIDS SimulationConfig schema.

    Allows autonomous agents to verify that AI-generated configuration files
    comply with all engine requirements (e.g., power-of-two grid bounds,
    matching species IDs) before attempting to launch a simulation.

    Args:
        config_json: The JSON string payload to validate.

    Returns:
        dict[str, Any]: A dictionary with a ``valid`` boolean and an ``errors`` list.
    """
    try:
        SimulationConfig.model_validate_json(config_json)
        return {"valid": True, "errors": []}
    except ValidationError as e:
        return {"valid": False, "errors": [err["msg"] for err in e.errors()]}
    except Exception as e:
        return {"valid": False, "errors": [str(e)]}


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
    loop = get_active_sim_loop()
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
def validate_okf_compliance() -> dict[str, Any]:
    """Run the OKF knowledge-graph validation suite against the docs/ and .agents/ trees.

    Invokes ``scripts/validate_okf.py`` via ``uv run`` from the project root,
    mirroring the pre-commit hook execution environment exactly. Essential for
    self-evolving agent loops to verify that documentation mutations remain
    structurally valid before opening a PR.

    Returns:
        dict[str, Any]: ``compliant`` (bool), ``violations`` (list of extracted
            error lines), and ``output`` (full captured stdout+stderr).
    """
    uv_bin = shutil.which("uv") or "uv"

    try:
        result = run_subprocess(
            [uv_bin, "run", "python", "scripts/validate_okf.py"],
            cwd=get_project_root(),
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
    return get_logs(limit=limit)
