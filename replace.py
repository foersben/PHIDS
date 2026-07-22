import re

with open("src/phids/api/routers/telemetry.py", "r") as f:
    content = f.read()

old_func = """@router.get("/api/telemetry/chartjs-data", summary="Per-species time-series data for Chart.js")
async def telemetry_chartjs_data(
    since_tick: int | None = None,
    run_id: str | None = None,
) -> JSONResponse:
    \"\"\"Return per-species population and energy time series for browser charts.

    Returns:
        JSONResponse: Chart.js-compatible labels, per-species identifiers, display names, and
        numeric series extracted from the live telemetry buffer.
    \"\"\"
    if api_main._sim_loop is None:
        return JSONResponse({"labels": [], "flora_ids": [], "herbivore_ids": [], "series": {}, "run_id": ""})

    current_run_id = api_main._sim_loop.run_id
    rows = api_main._sim_loop.telemetry._rows
    if run_id == current_run_id and since_tick is not None and rows:
        latest_tick = int(rows[-1].get("tick", -1))
        # When the simulation was reset, client-side since_tick can be ahead of
        # the current run; return full rows so chart state can re-synchronize.
        if latest_tick >= since_tick:
            rows = [row for row in rows if int(row.get("tick", -1)) > since_tick]
    species = api_main._sim_loop.telemetry.get_species_ids()
    flora_ids = species["flora_ids"]
    herbivore_ids = species["herbivore_ids"]

    flora_names = {sp.species_id: sp.name for sp in api_main._sim_loop.config.flora_species}
    herbivore_names = {sp.species_id: sp.name for sp in api_main._sim_loop.config.herbivore_species}

    labels = [r["tick"] for r in rows]
    series: dict[str, list[float]] = {
        "flora_population": [_safe_float(r.get("flora_population", 0)) for r in rows],
        "herbivore_population": [_safe_float(r.get("herbivore_population", 0)) for r in rows],
        "total_flora_energy": [_safe_float(r.get("total_flora_energy", 0.0)) for r in rows],
    }
    for fid in flora_ids:
        series[f"plant_{fid}_pop"] = [_safe_float(r.get("plant_pop_by_species", {}).get(fid, 0)) for r in rows]
        series[f"plant_{fid}_energy"] = [_safe_float(r.get("plant_energy_by_species", {}).get(fid, 0.0)) for r in rows]
        series[f"defense_cost_{fid}"] = [_safe_float(r.get("defense_cost_by_species", {}).get(fid, 0.0)) for r in rows]
    for hid in herbivore_ids:
        series[f"swarm_{hid}_pop"] = [_safe_float(r.get("swarm_pop_by_species", {}).get(hid, 0)) for r in rows]

    return JSONResponse(
        {
            "labels": labels,
            "flora_ids": flora_ids,
            "herbivore_ids": herbivore_ids,
            "flora_names": {str(k): v for k, v in flora_names.items()},
            "herbivore_names": {str(k): v for k, v in herbivore_names.items()},
            "series": series,
            "run_id": current_run_id,
        }
    )"""

new_func = """def _filter_telemetry_rows_for_chart(
    rows: list[dict[str, object]],
    run_id: str | None,
    current_run_id: str,
    since_tick: int | None,
) -> list[dict[str, object]]:
    \"\"\"Filter telemetry rows based on client synchronization state.\"\"\"
    if run_id == current_run_id and since_tick is not None and rows:
        latest_tick = int(rows[-1].get("tick", -1))
        if latest_tick >= since_tick:
            return [row for row in rows if int(row.get("tick", -1)) > since_tick]
    return rows


def _extract_chart_series(
    rows: list[dict[str, object]],
    flora_ids: list[int],
    herbivore_ids: list[int],
) -> tuple[list[int], dict[str, list[float]]]:
    \"\"\"Extract numerical time series and labels from raw telemetry rows.\"\"\"
    labels: list[int] = []
    series: dict[str, list[float]] = {
        "flora_population": [],
        "herbivore_population": [],
        "total_flora_energy": [],
    }
    for fid in flora_ids:
        series[f"plant_{fid}_pop"] = []
        series[f"plant_{fid}_energy"] = []
        series[f"defense_cost_{fid}"] = []
    for hid in herbivore_ids:
        series[f"swarm_{hid}_pop"] = []

    for r in rows:
        # Note: We must retain original exact values where possible; some tests assert strict arrays.
        tick_val = int(r.get("tick", 0))  # type: ignore
        labels.append(tick_val)
        series["flora_population"].append(_safe_float(r.get("flora_population", 0)))
        series["herbivore_population"].append(_safe_float(r.get("herbivore_population", 0)))
        series["total_flora_energy"].append(_safe_float(r.get("total_flora_energy", 0.0)))

        plant_pop = r.get("plant_pop_by_species", {})
        plant_energy = r.get("plant_energy_by_species", {})
        defense_cost = r.get("defense_cost_by_species", {})
        if isinstance(plant_pop, dict) and isinstance(plant_energy, dict) and isinstance(defense_cost, dict):
            for fid in flora_ids:
                series[f"plant_{fid}_pop"].append(_safe_float(plant_pop.get(fid, 0)))
                series[f"plant_{fid}_energy"].append(_safe_float(plant_energy.get(fid, 0.0)))
                series[f"defense_cost_{fid}"].append(_safe_float(defense_cost.get(fid, 0.0)))

        swarm_pop = r.get("swarm_pop_by_species", {})
        if isinstance(swarm_pop, dict):
            for hid in herbivore_ids:
                series[f"swarm_{hid}_pop"].append(_safe_float(swarm_pop.get(hid, 0)))

    return labels, series


@router.get("/api/telemetry/chartjs-data", summary="Per-species time-series data for Chart.js")
async def telemetry_chartjs_data(
    since_tick: int | None = None,
    run_id: str | None = None,
) -> JSONResponse:
    \"\"\"Return per-species population and energy time series for browser charts.

    Returns:
        JSONResponse: Chart.js-compatible labels, per-species identifiers, display names, and
        numeric series extracted from the live telemetry buffer.
    \"\"\"
    if api_main._sim_loop is None:
        return JSONResponse({"labels": [], "flora_ids": [], "herbivore_ids": [], "series": {}, "run_id": ""})

    current_run_id = api_main._sim_loop.run_id
    raw_rows = api_main._sim_loop.telemetry._rows
    rows = _filter_telemetry_rows_for_chart(raw_rows, run_id, current_run_id, since_tick)

    species = api_main._sim_loop.telemetry.get_species_ids()
    flora_ids = species["flora_ids"]
    herbivore_ids = species["herbivore_ids"]

    flora_names = {sp.species_id: sp.name for sp in api_main._sim_loop.config.flora_species}
    herbivore_names = {sp.species_id: sp.name for sp in api_main._sim_loop.config.herbivore_species}

    labels, series = _extract_chart_series(rows, flora_ids, herbivore_ids)

    return JSONResponse(
        {
            "labels": labels,
            "flora_ids": flora_ids,
            "herbivore_ids": herbivore_ids,
            "flora_names": {str(k): v for k, v in flora_names.items()},
            "herbivore_names": {str(k): v for k, v in herbivore_names.items()},
            "series": series,
            "run_id": current_run_id,
        }
    )"""

content = content.replace(old_func, new_func)
with open("src/phids/api/routers/telemetry.py", "w") as f:
    f.write(content)
print("Done")
