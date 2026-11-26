# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Unit tests for the headless batch and batch-inspect CLI subcommands."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from typer.testing import CliRunner

from phids.__main__ import app
from phids.api.schemas.placement import InitialPlantPlacement, InitialSwarmPlacement
from phids.api.schemas.simulation import SimulationConfig
from phids.api.schemas.species import (
    DietCompatibilityMatrix,
    FloraSpeciesParams,
    HerbivoreSpeciesParams,
)

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()


def _write_minimal_scenario(path: Path) -> None:
    """Persist a tiny valid SimulationConfig JSON for fast headless batch tests."""
    config = SimulationConfig(
        grid_width=16,
        grid_height=16,
        max_ticks=10,
        num_signals=1,
        num_toxins=1,
        flora_species=[
            FloraSpeciesParams(
                species_id=0,
                name="Grass",
                base_energy=20.0,
                max_energy=60.0,
                growth_rate=0.5,
                survival_threshold=2.0,
                reproduction_interval=20,
                seed_min_energy=40.0,
                seed_energy_cost=5.0,
            )
        ],
        herbivore_species=[
            HerbivoreSpeciesParams(
                species_id=0,
                name="Grazer",
                energy_min=1.0,
                velocity=1,
                consumption_rate=1.0,
                reproduction_energy_divisor=2.0,
                split_population_threshold=20,
            )
        ],
        diet_matrix=DietCompatibilityMatrix(rows=[[True]]),
        initial_plants=[InitialPlantPlacement(species_id=0, x=4, y=4, energy=20.0)],
        initial_swarms=[InitialSwarmPlacement(species_id=0, x=4, y=4, population=4, energy=10.0)],
    )
    path.write_text(json.dumps(config.model_dump(mode="json")), encoding="utf-8")


def test_cli_help_lists_batch_commands() -> None:
    """Verify top-level CLI help advertises batch and batch-inspect subcommands."""
    res = runner.invoke(app, ["--help"])
    assert res.exit_code == 0
    assert "batch" in res.stdout
    assert "batch-inspect" in res.stdout


def test_cli_batch_and_inspect_round_trip(tmp_path: Path) -> None:
    """Verify phids batch writes summary + exports and batch-inspect reads them cleanly."""
    scenario_path = tmp_path / "mini.json"
    out_dir = tmp_path / "batches"
    _write_minimal_scenario(scenario_path)

    res = runner.invoke(
        app,
        [
            "batch",
            str(scenario_path),
            "--runs",
            "2",
            "--max-ticks",
            "4",
            "--label",
            "smoke_label",
            "--output-dir",
            str(out_dir),
            "--export",
            "both",
            "--job-id",
            "job_smoke",
        ],
    )
    assert res.exit_code == 0, res.output
    summary_path = out_dir / "job_smoke_summary.json"
    assert summary_path.exists()
    assert (out_dir / "job_smoke.csv").exists()
    assert (out_dir / "job_smoke_table.tex").exists()

    summary_data = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary_data["scenario_name"] == "smoke_label"
    assert summary_data["runs_completed"] == 2

    inspect_res = runner.invoke(
        app,
        [
            "batch-inspect",
            "job_smoke",
            "--output-dir",
            str(out_dir),
            "--scenario",
            str(scenario_path),
            "--export",
            "csv",
        ],
    )
    assert inspect_res.exit_code == 0, inspect_res.output
    assert "smoke_label" in inspect_res.stdout
    assert "Runs: 2" in inspect_res.stdout


def test_cli_batch_missing_scenario_fails(tmp_path: Path) -> None:
    """Verify missing scenario path exits cleanly with status 1."""
    res = runner.invoke(app, ["batch", str(tmp_path / "missing.json")])
    assert res.exit_code == 1
