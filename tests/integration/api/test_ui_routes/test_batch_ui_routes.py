# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Integration tests for PHIDS Monte Carlo batch execution and academic export endpoints.

This module validates batch runner initiation, error rejection for empty scenario drafts,
status ledger updates, and CSV / TeX / TikZ academic telemetry exports.
"""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any

import pytest
from httpx import AsyncClient

import phids.api.main as api_main
from phids.api.services.draft.placements import add_plant_placement, add_swarm_placement
from phids.api.ui_state.state import get_draft, reset_draft
from phids.engine import batch as batch_engine

if TYPE_CHECKING:
    from collections.abc import Coroutine
    from pathlib import Path


@pytest.mark.asyncio
async def test_batch_start_rejects_invalid_draft(api_client: AsyncClient) -> None:
    """Verify batch start returns 400 when the draft lacks both flora and herbivore species."""
    reset_draft()
    invalid_draft = get_draft()
    invalid_draft.flora_species.clear()
    invalid_draft.herbivore_species.clear()

    resp = await api_client.post(
        "/api/batch/start",
        json={"runs": 1, "max_ticks": 2, "scenario_name": "invalid"},
    )

    assert resp.status_code == 400, resp.text
    assert "Invalid draft" in resp.text


def _patch_completed_batch_execution(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> list[asyncio.Task[None]]:
    """Patch batch execution to complete asynchronously with deterministic aggregate output."""
    reset_draft()
    draft = get_draft()
    add_plant_placement(draft, 0, 1, 1, 12.0)
    add_swarm_placement(draft, 0, 1, 1, 4, 16.0)
    monkeypatch.setattr(api_main, "_BATCH_DIR", tmp_path)

    scheduled_tasks: list[asyncio.Task[None]] = []
    original_create_task = asyncio.create_task

    def _capture_task(coro: Coroutine[Any, Any, None]) -> asyncio.Task[None]:
        task = original_create_task(coro)
        scheduled_tasks.append(task)
        return task

    def _fake_execute_batch(
        _self: batch_engine.BatchRunner,
        _scenario_dict: dict[str, object],
        runs: int,
        _max_ticks: int,
        job_id: str,
        output_dir: Path,
        on_progress: object | None = None,
        scenario_name: str | None = None,  # noqa: ARG001
    ) -> batch_engine.BatchResult:
        if callable(on_progress):
            on_progress(1)
            on_progress(runs)
        aggregate = {
            "ticks": [0, 1],
            "flora_population_mean": [10.0, 8.0],
            "flora_population_std": [0.0, 1.0],
            "herbivore_population_mean": [4.0, 5.0],
            "herbivore_population_std": [0.0, 1.0],
            "survival_probability_curve": [1.0, 0.5],
            "extinction_probability": 0.25,
            "runs_completed": runs,
            "per_flora_pop_mean": {"0": [10.0, 8.0]},
            "per_flora_pop_std": {"0": [0.0, 1.0]},
            "per_herbivore_pop_mean": {"0": [4.0, 5.0]},
            "per_herbivore_pop_std": {"0": [0.0, 1.0]},
        }
        (output_dir / f"{job_id}_summary.json").write_text(json.dumps(aggregate), encoding="utf-8")
        return batch_engine.BatchResult(
            job_id=job_id,
            runs=runs,
            per_run_telemetry=[],
            aggregate=aggregate,
        )

    monkeypatch.setattr(api_main.asyncio, "create_task", _capture_task)
    monkeypatch.setattr("phids.engine.batch.BatchRunner.execute_batch", _fake_execute_batch)
    return scheduled_tasks


@pytest.mark.asyncio
async def test_batch_status_ledger_and_view_routes_for_completed_job(
    api_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Verify completed batch jobs are visible in status, ledger, and aggregate view endpoints."""
    scheduled_tasks = _patch_completed_batch_execution(monkeypatch, tmp_path)

    start_resp = await api_client.post(
        "/api/batch/start",
        json={"runs": 2, "max_ticks": 3, "scenario_name": "coverage batch"},
    )
    assert start_resp.status_code == 200, start_resp.text
    job_id = start_resp.json()["job_id"]

    await asyncio.gather(*scheduled_tasks)
    status_resp = await api_client.get(f"/api/batch/status/{job_id}")
    ledger_resp = await api_client.get("/api/batch/ledger")
    view_resp = await api_client.get(f"/api/batch/view/{job_id}")

    assert status_resp.status_code == 200, status_resp.text
    assert "coverage batch" in status_resp.text
    assert ledger_resp.status_code == 200, ledger_resp.text
    assert job_id in ledger_resp.text
    assert view_resp.status_code == 200, view_resp.text
    assert "batch-survival-chart" in view_resp.text


@pytest.mark.parametrize(
    ("params", "expected_fragment"),
    [
        (
            {"format": "csv", "columns": "tick,flora_population_mean", "tick_interval": 1},
            "flora_population_mean",
        ),
        ({"format": "tex_table", "tick_interval": 1}, "\\toprule"),
        (
            {"format": "tex_tikz", "chart_type": "survival", "title": "Survival"},
            "Simulations alive (%)",
        ),
    ],
)
@pytest.mark.asyncio
async def test_batch_export_routes_support_csv_table_and_tikz(
    api_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    params: dict[str, str | int],
    expected_fragment: str,
) -> None:
    """Verify completed batches export expected CSV, TeX table, and TikZ chart payloads."""
    scheduled_tasks = _patch_completed_batch_execution(monkeypatch, tmp_path)

    start_resp = await api_client.post(
        "/api/batch/start",
        json={"runs": 2, "max_ticks": 3, "scenario_name": "coverage batch"},
    )
    assert start_resp.status_code == 200, start_resp.text
    job_id = start_resp.json()["job_id"]

    await asyncio.gather(*scheduled_tasks)
    resp = await api_client.get(f"/api/batch/export/{job_id}", params=params)

    assert resp.status_code == 200, resp.text
    assert expected_fragment in resp.text


@pytest.mark.parametrize(
    ("path_template", "params", "expected_status"),
    [
        ("/api/batch/status/does-not-exist", None, 404),
        ("/api/batch/export/does-not-exist", None, 404),
        ("/api/batch/export/{job_id}", {"format": "png"}, 400),
        ("/api/batch/export/{job_id}", {"format": "csv", "tick_interval": 0}, 400),
    ],
)
@pytest.mark.asyncio
async def test_batch_routes_return_errors_for_missing_job_and_invalid_export_params(
    api_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    path_template: str,
    params: dict[str, str | int] | None,
    expected_status: int,
) -> None:
    """Verify missing jobs and invalid export parameters return documented 404/400 responses."""
    scheduled_tasks = _patch_completed_batch_execution(monkeypatch, tmp_path)

    start_resp = await api_client.post(
        "/api/batch/start",
        json={"runs": 2, "max_ticks": 3, "scenario_name": "coverage batch"},
    )
    assert start_resp.status_code == 200, start_resp.text
    job_id = start_resp.json()["job_id"]

    await asyncio.gather(*scheduled_tasks)
    target_path = path_template.format(job_id=job_id)
    resp = await api_client.get(target_path, params=params)

    assert resp.status_code == expected_status, resp.text
