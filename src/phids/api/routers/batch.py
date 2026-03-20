"""Batch simulation router for PHIDS Monte Carlo workflows.

This module hosts the asynchronous batch-analysis endpoints that execute repeated headless
simulations, persist aggregate summaries, and render HTMX fragments for progress and post-run
inspection. The computation remains deterministic per run, while the batch surface provides
statistical aggregation over replicate trajectories to study extinction risk, biomass envelopes,
and survival probabilities. The router keeps a conservative coupling to `phids.api.main` so shared
application state and templates remain centralized during the ongoing refactor.
"""

from __future__ import annotations

import asyncio
import datetime
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response

import phids.api.main as api_main
from phids.api.schemas import BatchJobState, BatchStartPayload
from phids.api.ui_state import get_draft
from phids.telemetry.export import decimate_dataframe, filter_dataframe_columns, generate_tikz_str

router = APIRouter()


def _load_aggregate_json(summary_path: Path) -> dict[str, object]:
    """Load one persisted aggregate JSON object, defaulting to an empty mapping on shape mismatch."""
    with summary_path.open(encoding="utf-8") as fp:
        payload = json.load(fp)
    if isinstance(payload, dict):
        return payload
    api_main.logger.warning("Unexpected aggregate payload type in %s", summary_path)
    return {}


def _as_list(value: object) -> list[object]:
    """Normalize aggregate array fields to list payloads."""
    return value if isinstance(value, list) else []


def _safe_float(value: object) -> float:
    """Return a finite float-like value for aggregate export rows."""
    if not isinstance(value, (str, bytes, bytearray, int, float)):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _discover_persisted_batches() -> list[BatchJobState]:
    """Discover persisted batch summaries and map them to UI job rows.

    Returns:
        list[BatchJobState]: Reconstructed job states from persisted aggregate files.
    """
    batch_dir = api_main._BATCH_DIR
    if not batch_dir.exists():
        return []

    discovered: list[BatchJobState] = []
    for summary_path in sorted(batch_dir.glob("*_summary.json")):
        job_id = summary_path.stem.removesuffix("_summary")
        try:
            with summary_path.open(encoding="utf-8") as fp:
                aggregate = json.load(fp)
        except Exception:
            api_main.logger.warning("Skipping unreadable batch summary file: %s", summary_path)
            continue

        runs_completed = int(aggregate.get("runs_completed", 1) or 1)
        ticks = aggregate.get("ticks", [])
        started_at = datetime.datetime.fromtimestamp(
            summary_path.stat().st_mtime,
            tz=datetime.timezone.utc,
        )
        discovered.append(
            BatchJobState(
                job_id=job_id,
                status="done",
                completed=runs_completed,
                total=runs_completed,
                scenario_name=str(aggregate.get("scenario_name") or f"persisted_{job_id}"),
                started_at=started_at.isoformat(),
                finished_at=started_at.isoformat(),
                max_ticks=len(ticks),
            )
        )
    return discovered


@router.post("/api/batch/start", summary="Start a Monte Carlo batch simulation job")
async def batch_start(payload: BatchStartPayload) -> JSONResponse:
    """Enqueue one Monte Carlo batch job for asynchronous execution.

    Args:
        payload: Batch execution settings including replicate count and tick horizon.

    Returns:
        JSONResponse: Identifier of the enqueued batch job.

    Raises:
        HTTPException: If the current draft cannot be compiled into a valid simulation config.
    """
    import datetime
    import uuid

    draft = get_draft()
    try:
        config = draft.build_sim_config()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid draft: {exc}") from exc

    job_id = str(uuid.uuid4())[:8]
    scenario_name = payload.scenario_name or draft.scenario_name
    job = BatchJobState(
        job_id=job_id,
        status="queued",
        completed=0,
        total=payload.runs,
        scenario_name=scenario_name,
        started_at=datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),
        max_ticks=payload.max_ticks,
    )
    draft.active_batch_jobs[job_id] = job
    api_main.logger.info(
        "Batch job %s enqueued (runs=%d, max_ticks=%d)",
        job_id,
        payload.runs,
        payload.max_ticks,
    )

    scenario_dict = config.model_dump()

    async def _run_batch() -> None:
        from phids.engine.batch import BatchRunner

        job.status = "running"
        try:
            api_main._BATCH_DIR.mkdir(parents=True, exist_ok=True)
            runner = BatchRunner()

            loop = asyncio.get_event_loop()

            def _progress(completed: int) -> None:
                job.completed = completed
                api_main.logger.debug(
                    "Batch job %s progress: %d/%d", job_id, completed, payload.runs
                )

            await loop.run_in_executor(
                None,
                lambda: runner.execute_batch(
                    scenario_dict,
                    payload.runs,
                    payload.max_ticks,
                    job_id,
                    api_main._BATCH_DIR,
                    _progress,
                    scenario_name=scenario_name,
                ),
            )
            job.status = "done"
            job.completed = payload.runs
        except Exception:
            api_main.logger.exception("Batch job %s failed", job_id)
            job.status = "failed"
        finally:
            import datetime as dt

            job.finished_at = dt.datetime.now(tz=dt.timezone.utc).isoformat()

    asyncio.create_task(_run_batch())
    return JSONResponse({"job_id": job_id})


@router.get(
    "/api/batch/status/{job_id}", response_class=HTMLResponse, summary="Batch job status row"
)
async def batch_status(request: Request, job_id: str) -> Response:
    """Render one HTMX status-row fragment for a batch job.

    Raises:
        HTTPException: If the requested job identifier does not exist in draft state.
    """
    draft = get_draft()
    job = draft.active_batch_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return api_main.templates.TemplateResponse(
        request,
        "partials/batch_job_row.html",
        {"job": job},
    )


@router.get("/api/batch/ledger", response_class=HTMLResponse, summary="Batch job ledger")
async def batch_ledger(request: Request) -> Response:
    """Render the HTMX ledger fragment listing all tracked batch jobs."""
    draft = get_draft()
    jobs = list(draft.active_batch_jobs.values())
    return api_main.templates.TemplateResponse(
        request,
        "partials/batch_ledger.html",
        {"jobs": jobs},
    )


@router.post(
    "/api/batch/load-persisted", summary="Load persisted batch summaries into the UI ledger"
)
async def batch_load_persisted() -> JSONResponse:
    """Load persisted batch summaries from disk into draft job registry."""
    draft = get_draft()
    loaded = 0
    for job in _discover_persisted_batches():
        if job.job_id not in draft.active_batch_jobs:
            draft.active_batch_jobs[job.job_id] = job
            loaded += 1
    api_main.logger.info("Loaded %d persisted batch jobs into UI ledger", loaded)
    return JSONResponse({"loaded": loaded, "total": len(draft.active_batch_jobs)})


@router.get("/api/batch/view/{job_id}", response_class=HTMLResponse, summary="Batch aggregate view")
async def batch_view(request: Request, job_id: str) -> Response:
    """Render aggregate statistics fragment for one batch job identifier."""
    draft = get_draft()
    job = draft.active_batch_jobs.get(job_id)
    summary_path = api_main._BATCH_DIR / f"{job_id}_summary.json"
    aggregate: dict[str, object] = {}
    if summary_path.exists():
        aggregate = _load_aggregate_json(summary_path)

    return api_main.templates.TemplateResponse(
        request,
        "partials/batch_view.html",
        {"job": job, "aggregate": aggregate, "job_id": job_id},
    )


@router.get(
    "/api/batch/export/{job_id}",
    summary="Export batch aggregate in academic formats",
)
async def batch_export(
    job_id: str,
    format: str = "csv",  # noqa: A002
    tick_interval: int = 1,
    columns: str | None = None,
    title: str | None = None,
    x_label: str | None = None,
    y_label: str | None = None,
    chart_type: str = "timeseries",
) -> Response:
    """Export one persisted batch aggregate as CSV, table TeX, or TikZ source.

    Raises:
        HTTPException: If the requested summary file is missing or parameters are invalid.
    """
    summary_path = api_main._BATCH_DIR / f"{job_id}_summary.json"
    if not summary_path.exists():
        raise HTTPException(status_code=404, detail=f"No summary found for job '{job_id}'.")

    aggregate = _load_aggregate_json(summary_path)

    from phids.telemetry.export import aggregate_to_dataframe

    df = aggregate_to_dataframe(aggregate)
    if tick_interval < 1:
        raise HTTPException(status_code=400, detail="tick_interval must be >= 1")
    df = filter_dataframe_columns(df, columns)
    df = decimate_dataframe(df, tick_interval)

    if format == "csv":
        data = df.to_csv(index=False).encode("utf-8")
        filename = f"phids_batch_{job_id}.csv"
        media_type = "text/csv"
    elif format == "tex_table":
        latex: str = df.to_latex(index=False, float_format="%.2f")
        data = latex.encode("utf-8")
        filename = f"phids_batch_{job_id}_table.tex"
        media_type = "text/plain"
    elif format == "tex_tikz":
        rows_agg: list[dict[str, object]] = []
        ticks = _as_list(aggregate.get("ticks", []))
        flora_mean = _as_list(aggregate.get("flora_population_mean", []))
        herbivore_mean = _as_list(aggregate.get("herbivore_population_mean", []))
        survival = _as_list(aggregate.get("survival_probability_curve", []))
        for i, t in enumerate(ticks):
            rows_agg.append(
                {
                    "tick": t,
                    "plant_pop_by_species": {0: flora_mean[i] if i < len(flora_mean) else 0},
                    "swarm_pop_by_species": {
                        0: herbivore_mean[i] if i < len(herbivore_mean) else 0
                    },
                    "survival_probability": _safe_float(survival[i]) if i < len(survival) else 0.0,
                }
            )
        normalized_chart_type = "survival_probability" if chart_type == "survival" else chart_type
        tikz = generate_tikz_str(
            rows_agg,
            normalized_chart_type,
            title=title,
            x_label=x_label,
            y_label=y_label,
        )
        data = tikz.encode("utf-8")
        filename = f"phids_batch_{job_id}.tex"
        media_type = "text/plain"
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown format '{format}'. Use csv, tex_table, or tex_tikz.",
        )

    api_main.logger.info("Batch export job=%s format=%s size=%d", job_id, format, len(data))
    return Response(
        content=data,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
