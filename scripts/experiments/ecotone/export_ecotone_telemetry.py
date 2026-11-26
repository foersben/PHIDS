# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Export genuine showcase telemetry, Zarr metrics, and cross-thread hashes for the ecotone scenario."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import numpy as np

from phids.api.schemas.simulation import SimulationConfig
from phids.engine.components.plant import PlantComponent
from phids.engine.components.substances import SubstanceComponent
from phids.engine.components.swarm import SwarmComponent
from phids.engine.loop import SimulationLoop
from phids.io.zarr_replay import ReplayBuffer
from phids.telemetry.export.structured import export_csv, export_json

REPO_ROOT = Path(__file__).resolve().parents[3]
ECOTONE_DIR = REPO_ROOT / "docs" / "latex" / "scientific_report" / "data" / "ecotone_256x256"
SCENARIO_DIR = REPO_ROOT / "examples" / "scenarios"
SCENARIO_256_PATH = SCENARIO_DIR / "riparian_meadow_ecotone_256x256.json"
SCENARIO_TWIN_PATH = SCENARIO_DIR / "riparian_meadow_ecotone_128x64_twin.json"


def _compute_run_hash(config_path: Path, ticks: int) -> str:
    """Run a seeded simulation for N ticks and return a canonical SHA-256 state digest."""
    cfg = SimulationConfig.model_validate(json.loads(config_path.read_text(encoding="utf-8")))
    random.seed(42)
    np.random.seed(42)
    loop = SimulationLoop(cfg, disable_replay=True)

    async def _step_all() -> None:
        for _ in range(ticks):
            res = await loop.step()
            if res.terminated:
                break

    asyncio.run(_step_all())

    hasher = hashlib.sha256()
    hasher.update(np.ascontiguousarray(loop.env.plant_energy_layer, dtype=np.float64).tobytes())
    hasher.update(np.ascontiguousarray(loop.env.signal_layers, dtype=np.float64).tobytes())
    hasher.update(np.ascontiguousarray(loop.env.toxin_layers, dtype=np.float64).tobytes())
    hasher.update(np.ascontiguousarray(loop.env.flow_field, dtype=np.float64).tobytes())
    df = loop.telemetry.dataframe
    hasher.update(df.write_csv().encode("utf-8"))
    return hasher.hexdigest()


def _verify_cross_thread_determinism(config_path: Path, ticks: int, threads: list[int]) -> dict[str, Any]:
    """Verify bit-exact SHA-256 digests across isolated worker-thread subprocesses."""
    hashes: dict[str, str] = {}
    for idx, n_threads in enumerate(threads):
        env = os.environ.copy()
        env["NUMBA_NUM_THREADS"] = str(n_threads)
        env["OMP_NUM_THREADS"] = str(n_threads)
        cmd = [
            sys.executable,
            __file__,
            "--hash-worker",
            str(config_path),
            str(ticks),
        ]
        out = subprocess.check_output(cmd, env=env, text=True).strip()
        label = f"p{n_threads}" if str(n_threads) not in hashes else f"p{n_threads}_repeat{idx}"
        hashes[label] = out
    unique_hashes = set(hashes.values())
    return {
        "ticks": ticks,
        "threads_tested": threads,
        "hashes": hashes,
        "digest": next(iter(unique_hashes)),
        "identical": len(unique_hashes) == 1,
    }


def _collect_subs_by_owner(loop: SimulationLoop) -> dict[int, list[int]]:
    """Map owning plant entity IDs to their active substance channel IDs."""
    subs_by_owner: dict[int, list[int]] = {}
    for ent in loop.world.query(SubstanceComponent):
        sc = ent.get_component(SubstanceComponent)
        if sc.active:
            subs_by_owner.setdefault(sc.owner_plant_id, []).append(sc.substance_id)
    return subs_by_owner


def _colocated_swarms(loop: SimulationLoop, x: int, y: int) -> list[dict[str, int]]:
    """Collect species ID and headcount for all swarms sharing tile ``(x, y)``."""
    co_swarms: list[dict[str, int]] = []
    for eid in loop.world.entities_at(x, y):
        if not loop.world.has_entity(eid):
            continue
        co = loop.world.get_entity(eid)
        if co is not None and co.has_component(SwarmComponent):
            sw = co.get_component(SwarmComponent)
            co_swarms.append({"species_id": sw.species_id, "population": sw.population})
    return co_swarms


def _score_inspector_plant(
    loop: SimulationLoop, p: PlantComponent, active_ids: list[int]
) -> tuple[float, dict[str, Any]] | None:
    """Compute telemetry interest score and snapshot payload for an active plant tile."""
    co_swarms = _colocated_swarms(loop, p.x, p.y)
    if not active_ids and not co_swarms:
        return None
    sig_sum = float(loop.env.signal_layers[:3, p.x, p.y].sum())
    tox_sum = float(loop.env.toxin_layers[:, p.x, p.y].sum())
    cmn_deg = len(p.mycorrhizal_connections)
    score = (
        10.0 * (1 if co_swarms else 0)
        + 5.0 * len(active_ids)
        + 2.0 * min(3, cmn_deg)
        + sig_sum
        + tox_sum
        + (3.0 if p.apparent_nutrition_factor < 1.0 else 0.0)
    )
    payload: dict[str, Any] = {
        "x": int(p.x),
        "y": int(p.y),
        "species_id": int(p.species_id),
        "plant_energy": round(float(p.energy), 3),
        "cmn_links": int(cmn_deg),
        "active_substances": sorted(active_ids),
        "signal_sum": round(sig_sum, 4),
        "toxin_sum": round(tox_sum, 4),
        "apparent_nutrition_factor": round(float(p.apparent_nutrition_factor), 3),
        "swarms": co_swarms,
    }
    return score, payload


def _find_inspector_cell(loop: SimulationLoop) -> dict[str, Any]:
    """Select an active plant cell with co-located swarm, active defense, VOCs, and CMN links."""
    subs_by_owner = _collect_subs_by_owner(loop)
    best_score = -1.0
    best_cell: dict[str, Any] = {"x": 0, "y": 0}
    for ent in loop.world.query(PlantComponent):
        p = ent.get_component(PlantComponent)
        evaluated = _score_inspector_plant(loop, p, subs_by_owner.get(p.entity_id, []))
        if evaluated is None:
            continue
        score, payload = evaluated
        if score > best_score:
            best_score = score
            best_cell = payload
    return best_cell


def _count_active_substances(loop: SimulationLoop) -> dict[int, int]:
    """Count active synthetic substance instances per channel index (0..8)."""
    active_subs = {i: 0 for i in range(9)}
    for ent in loop.world.query(SubstanceComponent):
        sc = ent.get_component(SubstanceComponent)
        if sc.active:
            active_subs[sc.substance_id] += 1
    return active_subs


def _evaluate_showcase_candidate(loop: SimulationLoop, tick: int, active_subs: dict[int, int]) -> dict[str, Any] | None:
    """Evaluate mid-run ecological coexistence metrics for showcase tick selection."""
    if not (96 <= tick <= 336):
        return None
    herb_pop = {i: 0 for i in range(5)}
    for ent in loop.world.query(SwarmComponent):
        sw = ent.get_component(SwarmComponent)
        herb_pop[sw.species_id] += sw.population
    flora_cnt = {i: 0 for i in range(6)}
    myco_edges = 0
    wdr_cnt = 0
    for ent in loop.world.query(PlantComponent):
        pl = ent.get_component(PlantComponent)
        flora_cnt[pl.species_id] += 1
        myco_edges += len(pl.mycorrhizal_connections)
        if pl.apparent_nutrition_factor < 1.0:
            wdr_cnt += 1
    if not (all(v > 0 for v in herb_pop.values()) and all(v > 0 for v in flora_cnt.values())):
        return None
    nonzero_channels = sum(1 for v in active_subs.values() if v > 0)
    score = nonzero_channels * 100.0 + sum(active_subs.values()) * 0.05 + wdr_cnt * 0.2 + (50.0 if tick >= 150 else 0.0)
    return {
        "tick": tick + 1,
        "score": score,
        "nonzero_channels": nonzero_channels,
        "active_substances": active_subs,
        "flora_counts": flora_cnt,
        "herbivore_pops": herb_pop,
        "myco_links": myco_edges // 2,
        "withdrawals": wdr_cnt,
    }


def _zarr_disk_bytes(cfg: SimulationConfig, loop: SimulationLoop, zarr_dir: Path) -> tuple[int, int, float]:
    """Compute raw float32 size, on-disk Zarr bytes, and compression ratio."""
    compressed_bytes = sum(f.stat().st_size for f in zarr_dir.rglob("*") if f.is_file())
    per_frame_floats = (5 + cfg.num_signals + cfg.num_toxins) * cfg.grid_width * cfg.grid_height
    assert loop.replay is not None
    raw_float32_bytes = len(loop.replay) * per_frame_floats * 4
    compression_ratio = raw_float32_bytes / max(1, compressed_bytes)
    return raw_float32_bytes, compressed_bytes, compression_ratio


async def _run_showcase_export() -> None:
    cfg = SimulationConfig.model_validate(json.loads(SCENARIO_256_PATH.read_text(encoding="utf-8")))
    random.seed(42)
    np.random.seed(42)
    loop = SimulationLoop(cfg, disable_replay=True)

    tmp_zarr = Path(tempfile.mkdtemp(prefix="phids_ecotone_zarr_"))
    zarr_dir = tmp_zarr / "replay.zarr"
    try:
        loop.replay = ReplayBuffer(max_frames=400, spill_path=zarr_dir)
        latencies_ms: list[float] = []
        candidates: list[dict[str, Any]] = []

        for t in range(360):
            t0 = time.perf_counter()
            res = await loop.step()
            latencies_ms.append((time.perf_counter() - t0) * 1000.0)
            candidate = _evaluate_showcase_candidate(loop, t, _count_active_substances(loop))
            if candidate is not None:
                candidates.append(candidate)
            if res.terminated:
                break

        best_candidate = max(candidates, key=lambda c: (c["nonzero_channels"], c["score"]))
        showcase_tick = int(best_candidate["tick"])

        df = loop.telemetry.dataframe
        export_csv(df, ECOTONE_DIR / "telemetry.csv")
        export_json(df, ECOTONE_DIR / "telemetry.ndjson")
        raw_float32_bytes, compressed_bytes, compression_ratio = _zarr_disk_bytes(cfg, loop, zarr_dir)
    finally:
        shutil.rmtree(tmp_zarr, ignore_errors=True)

    random.seed(42)
    np.random.seed(42)
    loop_show = SimulationLoop(cfg, disable_replay=True)
    for _ in range(showcase_tick):
        await loop_show.step()
    inspector_cell = _find_inspector_cell(loop_show)

    steady_lat = latencies_ms[10:]
    summary = {
        "scenario": "Central European Riparian-to-Floodplain-Meadow Ecotone",
        "grid_width": cfg.grid_width,
        "grid_height": cfg.grid_height,
        "ticks_simulated": len(latencies_ms),
        "showcase_tick": showcase_tick,
        "showcase_state": best_candidate,
        "inspector_cell": inspector_cell,
        "latency_ms": {
            "median": round(float(np.median(steady_lat)), 3),
            "p95": round(float(np.percentile(steady_lat, 95)), 3),
            "mean": round(float(np.mean(steady_lat)), 3),
        },
        "zarr_replay": {
            "frames": 360,
            "raw_float32_mb": round(raw_float32_bytes / (1024.0 * 1024.0), 3),
            "compressed_mb": round(compressed_bytes / (1024.0 * 1024.0), 3),
            "compression_ratio": round(compression_ratio, 2),
        },
        "telemetry_rows": int(df.height),
        "telemetry_columns": list(df.columns),
        "determinism": {
            "twin_128x64": _verify_cross_thread_determinism(SCENARIO_TWIN_PATH, 200, [1, 4, 12, 1]),
            "flagship_256x256": _verify_cross_thread_determinism(SCENARIO_256_PATH, 50, [1, 4, 12, 1]),
        },
    }
    summary_path = ECOTONE_DIR / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


def main() -> None:
    """Dispatch either determinism hash worker or full telemetry export."""
    if len(sys.argv) == 4 and sys.argv[1] == "--hash-worker":
        print(_compute_run_hash(Path(sys.argv[2]), int(sys.argv[3])))
        return
    asyncio.run(_run_showcase_export())


if __name__ == "__main__":
    main()
