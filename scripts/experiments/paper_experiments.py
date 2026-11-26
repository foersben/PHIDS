# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial
# mypy: ignore-errors

"""Reproducible experiments backing the PHIDS journal manuscript.

Every quantitative statement and every data-driven figure in
``docs/latex/scientific_report`` must trace back to a JSON artefact written by
this script into ``docs/latex/scientific_report/data``. The script drives the
production engine (``phids.engine``) headlessly; it never synthesises
trajectories.

Sub-commands:

* ``dynamics``    - ensemble of the reference scenario (Section 7.1).
* ``priming``     - Theorem 2 latency threshold and orchard toxin-latency sweep (Section 7.2).
* ``ablation``    - signalling ablation and wind sweep (Sections 7.2 and 7.3).
* ``crossover``   - airborne VOC vs mycorrhizal upwind/downwind propagation (Section 7.3).
* ``sobol``       - variance-based global sensitivity analysis (Section 7.4).
* ``perf``        - steady-state tick cost, thread scaling, micro-benchmarks,
  replay compression and bit-exact determinism (Section 8).
* ``all``         - run every experiment in sequence.

Usage::

    uv run python scripts/experiments/paper_experiments.py all
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import json
import logging
import multiprocessing as mp
import os
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "docs" / "latex" / "scientific_report" / "data"
EXAMPLES = ROOT / "examples"
REFERENCE_SCENARIO = "wind_tunnel_orchard"
N_SEEDS = 12


def _load(name: str) -> dict[str, Any]:
    """Load an example scenario by name."""
    with (EXAMPLES / f"{name}.json").open() as handle:
        return json.load(handle)  # type: ignore[no-any-return]


def _save(name: str, payload: dict[str, Any]) -> None:
    """Persist an experiment artefact as JSON."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with (DATA_DIR / f"{name}.json").open("w") as handle:
        json.dump(payload, handle)
    print(f"wrote {DATA_DIR / (name + '.json')}")


def _init_worker() -> None:
    """Pin every worker to one Numba thread to avoid oversubscription."""
    os.environ["NUMBA_NUM_THREADS"] = "1"
    logging.disable(logging.CRITICAL)


def _extract_species_series(
    rows: list[dict[str, Any]], field: str, n_species: int, default: float | int
) -> list[list[Any]]:
    """Extract nested per-species metrics across ticks."""
    return [[r[field].get(i, default) for i in range(n_species)] for r in rows]


def _extract_death_metrics(rows: list[dict[str, Any]]) -> dict[str, int]:
    """Aggregate cumulative mortality metrics from telemetry rows."""
    deaths: dict[str, int] = {}
    if not rows:
        return deaths
    for key in rows[-1]:
        if key.startswith("death_"):
            deaths[key] = int(sum(r[key] for r in rows))
    return deaths


def _run_one(job: tuple[dict[str, Any], int, int]) -> dict[str, Any]:
    """Run one headless simulation and compress its telemetry into arrays."""
    scenario, ticks, seed = job
    from phids.engine.batch.runner import _run_single_headless

    rows = _run_single_headless(scenario, ticks, seed)
    n_flora = len(scenario["flora_species"])
    n_herb = len(scenario["herbivore_species"])
    out: dict[str, Any] = {
        "seed": seed,
        "ticks": len(rows),
        "max_ticks": ticks,
        "flora_pop": [r["flora_population"] for r in rows],
        "herb_pop": [r["herbivore_population"] for r in rows],
        "flora_energy": [r["total_flora_energy"] for r in rows],
        "plant_pop_by_species": _extract_species_series(rows, "plant_pop_by_species", n_flora, 0),
        "plant_energy_by_species": _extract_species_series(rows, "plant_energy_by_species", n_flora, 0.0),
        "swarm_pop_by_species": _extract_species_series(rows, "swarm_pop_by_species", n_herb, 0),
    }
    out.update(_extract_death_metrics(rows))
    return out


def _pool_map(jobs: list[tuple[dict[str, Any], int, int]]) -> list[dict[str, Any]]:
    """Execute jobs on a spawn-context process pool."""
    ctx = mp.get_context("spawn")
    with ProcessPoolExecutor(max_workers=os.cpu_count(), mp_context=ctx, initializer=_init_worker) as pool:
        return list(pool.map(_run_one, jobs, chunksize=1))


def _without_signalling(scenario: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of ``scenario`` with every flora trigger removed."""
    clone = copy.deepcopy(scenario)
    for species in clone["flora_species"]:
        species["triggers"] = []
    return clone


def run_dynamics() -> None:
    """Ensemble of the reference scenario for the coexistence analysis."""
    base = _load(REFERENCE_SCENARIO)
    horizon = 4000
    base_4k = copy.deepcopy(base)
    base_4k["max_ticks"] = horizon
    jobs = [(base_4k, horizon, seed) for seed in range(N_SEEDS)]
    runs = _pool_map(jobs)
    _save(
        "dynamics",
        {
            "scenario": REFERENCE_SCENARIO,
            "grid": [base["grid_width"], base["grid_height"]],
            "flora": [s["name"] for s in base["flora_species"]],
            "herbivores": [s["name"] for s in base["herbivore_species"]],
            "runs": runs,
        },
    )


def _summarise(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate outcome metrics across an ensemble."""
    tail = []
    persisted = 0
    feeding = []
    herb_tail = []
    for run in runs:
        half = len(run["flora_pop"]) // 2
        tail.append(float(np.mean(run["flora_energy"][half:])))
        herb_tail.append(float(np.mean(run["herb_pop"][half:])))
        persisted += int(run["ticks"] == run["max_ticks"])
        feeding.append(run.get("death_herbivore_feeding", 0))
    return {
        "n": len(runs),
        "persisted": persisted,
        "flora_energy_tail_mean": float(np.mean(tail)),
        "flora_energy_tail_sd": float(np.std(tail, ddof=1)),
        "herb_tail_mean": float(np.mean(herb_tail)),
        "feeding_deaths_mean": float(np.mean(feeding)),
        "feeding_deaths_sd": float(np.std(feeding, ddof=1)),
    }


def _priming_threshold_case(theta: int) -> dict[str, Any]:
    """Verify Theorem 2 under hourly continuous Holling Type II grazing in phids.engine."""
    import random

    logging.disable(logging.CRITICAL)
    from phids.api.schemas.simulation import SimulationConfig
    from phids.engine.components.plant import PlantComponent
    from phids.engine.components.swarm import SwarmComponent
    from phids.engine.loop import SimulationLoop

    cfg_dict: dict[str, Any] = {
        "grid_width": 16,
        "grid_height": 16,
        "max_ticks": 24,
        "tick_rate_hz": 10.0,
        "num_signals": 2,
        "num_toxins": 2,
        "wind_x": 0.0,
        "wind_y": 0.0,
        "substance_emit_rate": 1.0,
        "signal_decay_factor": 0.9,
        "mycorrhizal_inter_species": False,
        "mycorrhizal_connection_cost": 1000.0,
        "mycorrhizal_growth_interval_ticks": 256,
        "mycorrhizal_signal_velocity": 1,
        "flora_species": [
            {
                "species_id": 0,
                "name": "Focal Flora",
                "base_energy": 50.0,
                "max_energy": 100.0,
                "growth_rate": 0.0,
                "survival_threshold": 10.0,
                "reproduction_interval": 9999,
                "seed_min_dist": 1.0,
                "seed_max_dist": 2.0,
                "seed_energy_cost": 5.0,
                "camouflage": False,
                "camouflage_factor": 1.0,
                "triggers": [
                    {
                        "aftereffect_ticks": 20,
                        "activation_condition": {
                            "kind": "herbivore_presence",
                            "herbivore_species_id": 0,
                            "min_herbivore_population": 1,
                        },
                        "action": {
                            "type": "synthesize_substance",
                            "substance_id": 0,
                            "synthesis_duration": theta,
                            "is_toxin": True,
                            "lethal": True,
                            "lethality_rate": 10.0,
                            "repellent": True,
                            "repellent_walk_ticks": 20,
                            "energy_cost_per_tick": 0.0,
                            "irreversible": False,
                        },
                        "initiator": {
                            "type": "herbivore_attack",
                            "herbivore_species_id": 0,
                            "min_herbivore_population": 1,
                        },
                    }
                ],
            }
        ],
        "herbivore_species": [
            {
                "species_id": 0,
                "name": "Focal Grazer",
                "base_energy": 20.0,
                "energy_min": 5.0,
                "energy_loss_per_tick": 0.0,
                "consumption_rate": 0.06,
                "handling_time": 0.30,
                "digestive_efficiency": 0.2,
                "velocity": 1,
                "reproduction_threshold": 1e9,
                "split_population_threshold": 1000,
                "repulsion_distance": 1.0,
            }
        ],
        "diet_matrix": {"rows": [[True]]},
        "initial_plants": [{"species_id": 0, "x": 8, "y": 8, "energy": 50.0}],
        "initial_swarms": [{"species_id": 0, "x": 8, "y": 8, "population": 25, "energy": 200.0}],
    }
    random.seed(0)
    np.random.seed(0)
    loop = SimulationLoop(SimulationConfig.model_validate(cfg_dict), disable_replay=True)
    survival_tick: int | None = None
    herb_extinct_tick: int | None = None
    for t in range(12):
        loop.tick = t
        p_deaths: dict[str, int] = {
            "death_reproduction": 0,
            "death_mycorrhiza": 0,
            "death_defense_maintenance": 0,
            "death_herbivore_feeding": 0,
            "death_background_deficit": 0,
        }
        h_deaths: dict[str, int] = {"death_starvation": 0, "death_lethal_toxin": 0}
        loop._step_phase_flow_field()
        loop._step_phase_interaction(p_deaths, h_deaths, is_medium_tick=True, is_slow_tick=False)
        loop._step_phase_signaling(p_deaths)
        plants = [e.get_component(PlantComponent) for e in loop.world.query(PlantComponent)]
        swarms = [e.get_component(SwarmComponent) for e in loop.world.query(SwarmComponent)]
        if not plants and survival_tick is None:
            survival_tick = t
        if not swarms and herb_extinct_tick is None:
            herb_extinct_tick = t
    plants_end = [e.get_component(PlantComponent) for e in loop.world.query(PlantComponent)]
    return {
        "theta_ticks": theta,
        "plant_survived": len(plants_end) > 0,
        "final_plant_energy": float(plants_end[0].energy) if plants_end else 0.0,
        "plant_death_tick": survival_tick,
        "herb_extinct_tick": herb_extinct_tick,
    }


def run_priming() -> None:
    """Section 7.2 Theorem 2 critical-latency verification and orchard toxin-delay sweep."""
    threshold_sweep = [_priming_threshold_case(theta) for theta in (1, 2, 3, 4)]

    base = _load(REFERENCE_SCENARIO)
    orchard_sweep: list[dict[str, Any]] = []
    for toxin_delay in (1, 2, 24, 36):
        scenario = copy.deepcopy(base)
        for flora in scenario["flora_species"]:
            for trig in flora["triggers"]:
                if trig["action"]["type"] == "synthesize_substance" and trig["action"]["is_toxin"]:
                    trig["action"]["synthesis_duration"] = toxin_delay
        runs = _pool_map([(scenario, base["max_ticks"], seed) for seed in range(N_SEEDS)])
        summary = _summarise(runs)
        summary["toxin_synthesis_duration"] = toxin_delay
        orchard_sweep.append(summary)
        print("priming orchard delay", toxin_delay, summary)

    _save(
        "priming",
        {
            "theorem2_params": {"E_crit": 50.0, "E_min": 10.0, "a": 0.06, "T_h": 0.30, "N": 25},
            "theta_exact_h": 1.552959,
            "theta_linear_h": 1.013333,
            "hourly_threshold_sweep": threshold_sweep,
            "orchard_toxin_delay_sweep": orchard_sweep,
        },
    )


def _crossover_active_coords(loop: Any, substance_comp_cls: Any, plant_comp_cls: Any) -> set[tuple[int, int]]:
    """Collect ``(x, y)`` coordinates of plants actively synthesising signal channel 0."""
    active_coords: set[tuple[int, int]] = set()
    for ent in loop.world.query(substance_comp_cls):
        sub = ent.get_component(substance_comp_cls)
        if not (sub.active and sub.substance_id == 0):
            continue
        owner = loop.world.get_entity(sub.owner_plant_id)
        if owner is not None:
            pc = owner.get_component(plant_comp_cls)
            active_coords.add((pc.x, pc.y))
    return active_coords


def _crossover_case(wind_x: float, mycorrhiza_enabled: bool) -> dict[str, Any]:
    """Run airborne VOC + optional mycorrhizal relay across directional wind in phids.engine."""
    import random

    logging.disable(logging.CRITICAL)
    from phids.api.schemas.simulation import SimulationConfig
    from phids.engine.components.plant import PlantComponent
    from phids.engine.components.substances import SubstanceComponent
    from phids.engine.loop import SimulationLoop

    plants = [{"species_id": 0, "x": x, "y": 16, "energy": 80.0} for x in range(29, 36)]
    cfg_dict: dict[str, Any] = {
        "grid_width": 64,
        "grid_height": 32,
        "max_ticks": 30,
        "tick_rate_hz": 10.0,
        "num_signals": 2,
        "num_toxins": 1,
        "wind_x": wind_x,
        "wind_y": 0.0,
        "substance_emit_rate": 0.5,
        "signal_decay_factor": 0.90,
        "mycorrhizal_inter_species": False,
        "mycorrhizal_connection_cost": 0.1 if mycorrhiza_enabled else 1000.0,
        "mycorrhizal_growth_interval_ticks": 1 if mycorrhiza_enabled else 256,
        "mycorrhizal_signal_velocity": 3,
        "flora_species": [
            {
                "species_id": 0,
                "name": "Relay Tree",
                "base_energy": 80.0,
                "max_energy": 120.0,
                "growth_rate": 0.0,
                "survival_threshold": 5.0,
                "reproduction_interval": 9999,
                "seed_min_dist": 1.0,
                "seed_max_dist": 2.0,
                "seed_energy_cost": 5.0,
                "camouflage": False,
                "camouflage_factor": 1.0,
                "triggers": [
                    {
                        "aftereffect_ticks": 30,
                        "activation_condition": {
                            "kind": "herbivore_presence",
                            "herbivore_species_id": 0,
                            "min_herbivore_population": 1,
                        },
                        "action": {
                            "type": "synthesize_substance",
                            "substance_id": 0,
                            "synthesis_duration": 1,
                            "is_toxin": False,
                            "lethal": False,
                            "lethality_rate": 0.0,
                            "repellent": False,
                            "repellent_walk_ticks": 0,
                            "energy_cost_per_tick": 0.0,
                            "irreversible": True,
                        },
                        "initiator": {
                            "type": "herbivore_attack",
                            "herbivore_species_id": 0,
                            "min_herbivore_population": 1,
                        },
                    },
                    {
                        "aftereffect_ticks": 30,
                        "activation_condition": None,
                        "action": {
                            "type": "synthesize_substance",
                            "substance_id": 0,
                            "synthesis_duration": 1,
                            "is_toxin": False,
                            "lethal": False,
                            "lethality_rate": 0.0,
                            "repellent": False,
                            "repellent_walk_ticks": 0,
                            "energy_cost_per_tick": 0.0,
                            "irreversible": True,
                        },
                        "initiator": {
                            "type": "environmental_signal",
                            "signal_id": 0,
                            "min_concentration": 0.01,
                            "response_curve": "step",
                            "hill_cooperativity": 2.0,
                            "half_saturation": 0.05,
                        },
                    },
                ],
            }
        ],
        "herbivore_species": [
            {
                "species_id": 0,
                "name": "Anchored Pest",
                "base_energy": 20.0,
                "energy_min": 5.0,
                "energy_loss_per_tick": 0.0,
                "consumption_rate": 0.001,
                "handling_time": 0.1,
                "digestive_efficiency": 0.0,
                "velocity": 1,
                "reproduction_threshold": 1e9,
                "split_population_threshold": 1000,
                "repulsion_distance": 1.0,
            }
        ],
        "diet_matrix": {"rows": [[True]]},
        "initial_plants": plants,
        "initial_swarms": [{"species_id": 0, "x": 32, "y": 16, "population": 2, "energy": 20.0}],
    }
    random.seed(0)
    np.random.seed(0)
    loop = SimulationLoop(SimulationConfig.model_validate(cfg_dict), disable_replay=True)

    state: dict[str, Any] = {
        "upwind_first_tick": None,
        "downwind_first_tick": None,
        "upwind_peak_c": 0.0,
        "downwind_peak_c": 0.0,
    }

    async def drive() -> None:
        for tick in range(20):
            await loop.step()
            state["upwind_peak_c"] = max(state["upwind_peak_c"], float(loop.env.signal_layers[0, 29, 16]))
            state["downwind_peak_c"] = max(state["downwind_peak_c"], float(loop.env.signal_layers[0, 35, 16]))
            active_coords = _crossover_active_coords(loop, SubstanceComponent, PlantComponent)
            if (29, 16) in active_coords and state["upwind_first_tick"] is None:
                state["upwind_first_tick"] = tick
            if (35, 16) in active_coords and state["downwind_first_tick"] is None:
                state["downwind_first_tick"] = tick

    asyncio.run(drive())
    return {"wind_x": wind_x, "mycorrhiza": mycorrhiza_enabled, **state}


def run_crossover() -> None:
    """Section 7.3 airborne-only vs mycorrhizal directional-wind propagation experiment."""
    winds = [0.0, 0.5, 1.05, 2.0, 3.0]
    rows = []
    for wind in winds:
        rows.append(_crossover_case(wind, False))
        rows.append(_crossover_case(wind, True))
        print("crossover wind", wind, rows[-2], rows[-1])
    _save("crossover", {"winds": winds, "horizon_ticks": 20, "rows": rows})


def run_ablation() -> None:
    """Signalling ablation across a wind sweep."""
    base = _load(REFERENCE_SCENARIO)
    winds = [0.0, 0.5, 1.05, 2.0, 3.0]
    result: dict[str, Any] = {"scenario": REFERENCE_SCENARIO, "winds": winds, "with_signalling": [], "without": []}
    for wind in winds:
        for label, builder in (("with_signalling", lambda s: s), ("without", _without_signalling)):
            scenario = builder(copy.deepcopy(base))
            scenario["wind_x"] = wind
            runs = _pool_map([(scenario, base["max_ticks"], seed) for seed in range(N_SEEDS)])
            result[label].append(_summarise(runs))
            print(label, wind, result[label][-1])
    _save("ablation", result)


def _scaled(base: dict[str, Any], theta: np.ndarray) -> dict[str, Any]:
    """Apply a unit-scaled parameter vector to a scenario copy."""
    scenario = copy.deepcopy(base)
    consume, growth, cost, emin, wind = theta
    for herb in scenario["herbivore_species"]:
        herb["consumption_rate"] *= consume
        herb["energy_min"] *= emin
    for flora in scenario["flora_species"]:
        flora["growth_rate"] *= growth
        for trig in flora["triggers"]:
            trig["action"]["energy_cost_per_tick"] *= cost
    scenario["wind_x"] = wind
    return scenario


SOBOL_FACTORS = [
    ("herbivore consumption rate", 0.6, 1.4),
    ("flora growth rate", 0.6, 1.4),
    ("defence cost per tick", 0.5, 2.0),
    ("herbivore starvation threshold", 0.6, 1.6),
    ("wind speed", 0.0, 2.5),
]


def _sobol_indices(f_a: np.ndarray, f_b: np.ndarray, f_ab: np.ndarray, rng: np.random.Generator) -> dict[str, Any]:
    """Saltelli (2010) first-order and Jansen total-order indices with bootstrap CIs."""
    n, _d = f_ab.shape

    def estimate(idx: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        a, b, ab = f_a[idx], f_b[idx], f_ab[idx]
        var = np.var(np.concatenate([a, b]), ddof=1)
        s1 = np.mean(b[:, None] * (ab - a[:, None]), axis=0) / var
        st = 0.5 * np.mean((a[:, None] - ab) ** 2, axis=0) / var
        return s1, st

    s1, st = estimate(np.arange(n))
    boots = [estimate(rng.integers(0, n, n)) for _ in range(1000)]
    s1_ci = np.percentile([b[0] for b in boots], [2.5, 97.5], axis=0)
    st_ci = np.percentile([b[1] for b in boots], [2.5, 97.5], axis=0)
    return {"S1": s1.tolist(), "ST": st.tolist(), "S1_ci": s1_ci.tolist(), "ST_ci": st_ci.tolist()}


def run_sobol(n_base: int = 256) -> None:
    """Variance-based global sensitivity analysis on the reference scenario."""
    from scipy.stats import qmc

    base = _load(REFERENCE_SCENARIO)
    d = len(SOBOL_FACTORS)
    sample = qmc.Sobol(d=2 * d, scramble=True, seed=7).random(n_base)
    lo = np.array([f[1] for f in SOBOL_FACTORS])
    hi = np.array([f[2] for f in SOBOL_FACTORS])
    mat_a = lo + sample[:, :d] * (hi - lo)
    mat_b = lo + sample[:, d:] * (hi - lo)
    rows = [mat_a, mat_b] + [np.where(np.arange(d) == i, mat_b, mat_a) for i in range(d)]
    jobs = [(_scaled(base, theta), base["max_ticks"], 0) for block in rows for theta in block]
    runs = _pool_map(jobs)

    def outcome(run: dict[str, Any]) -> tuple[float, float]:
        half = len(run["flora_energy"]) // 2
        return float(np.mean(run["flora_energy"][half:])), run["ticks"] / run["max_ticks"]

    values = np.array([outcome(r) for r in runs])
    result: dict[str, Any] = {
        "factors": [f[0] for f in SOBOL_FACTORS],
        "n_base": n_base,
        "runs": len(runs),
        "outputs": {},
    }
    rng = np.random.default_rng(11)
    for col, name in enumerate(("mean_flora_energy", "persistence_fraction")):
        y = values[:, col]
        f_a, f_b = y[:n_base], y[n_base : 2 * n_base]
        f_ab = np.stack([y[(2 + i) * n_base : (3 + i) * n_base] for i in range(d)], axis=1)
        result["outputs"][name] = _sobol_indices(f_a, f_b, f_ab, rng)
        result["outputs"][name]["mean"] = float(np.mean(y))
        result["outputs"][name]["sd"] = float(np.std(y, ddof=1))
    _save("sobol", result)


# ---------------------------------------------------------------------------
# Performance and determinism (Section 8)
# ---------------------------------------------------------------------------


def _perf_worker(scenario_name: str, warmup: int, measured: int) -> None:
    """Measure steady-state tick cost in this process and print one JSON line."""
    logging.disable(logging.CRITICAL)
    from numba import get_num_threads

    from phids.api.schemas.simulation import SimulationConfig
    from phids.engine.loop import SimulationLoop

    scenario = _load(scenario_name)
    loop = SimulationLoop(SimulationConfig.model_validate(scenario), disable_replay=True)

    async def drive() -> list[float]:
        stamps: list[float] = []
        for i in range(warmup + measured):
            t0 = time.perf_counter()
            result = await loop.step()
            if i >= warmup:
                stamps.append(time.perf_counter() - t0)
            if result.terminated:
                break
        return stamps

    stamps = asyncio.run(drive())
    plants = int(loop.telemetry._rows[-1]["flora_population"])
    print(
        json.dumps(
            {
                "scenario": scenario_name,
                "grid": [scenario["grid_width"], scenario["grid_height"]],
                "threads": int(get_num_threads()),
                "plants_end": plants,
                "ticks_measured": len(stamps),
                "ms_per_tick_median": 1000 * float(np.median(stamps)) if stamps else None,
                "ms_per_tick_p95": 1000 * float(np.percentile(stamps, 95)) if stamps else None,
            }
        )
    )


def _spawn_perf(scenario: str, threads: int, warmup: int, measured: int) -> dict[str, Any]:
    """Run ``_perf_worker`` in a fresh interpreter with a fixed Numba thread count."""
    env = dict(os.environ)
    if threads > 0:
        env["NUMBA_NUM_THREADS"] = str(threads)
    else:
        env.pop("NUMBA_NUM_THREADS", None)
    proc = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "perf-worker", scenario, str(warmup), str(measured)],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(proc.stdout.strip().splitlines()[-1])  # type: ignore[no-any-return]


def _microbench_wrap() -> dict[str, float]:
    """Compare modulo and bit-mask toroidal wrapping inside Numba kernels."""
    from numba import njit

    @njit(cache=False)
    def wrap_mod(xs: np.ndarray, width: int, out: np.ndarray) -> None:
        for i in range(xs.shape[0]):
            out[i] = xs[i] % width

    @njit(cache=False)
    def wrap_mask(xs: np.ndarray, width: int, out: np.ndarray) -> None:
        for i in range(xs.shape[0]):
            out[i] = xs[i] & (width - 1)

    rng = np.random.default_rng(0)
    xs = rng.integers(-4096, 4096, 20_000_000).astype(np.int64)
    out = np.empty_like(xs)
    best: dict[str, float] = {}
    for name, fn in (("modulo", wrap_mod), ("bitmask", wrap_mask)):
        fn(xs[:8], 256, out[:8])
        samples = []
        for _ in range(15):
            t0 = time.perf_counter()
            fn(xs, 256, out)
            samples.append(time.perf_counter() - t0)
        best[name] = 1e9 * float(np.median(samples)) / xs.shape[0]
    check = np.empty_like(xs)
    wrap_mod(xs, 256, check)
    wrap_mask(xs, 256, out)
    best["identical"] = float(np.array_equal(check, out))
    return best


def _replay_compression(scenario_name: str, ticks: int) -> dict[str, Any]:
    """Measure on-disk Zarr size against raw float32 field volume for a real run."""
    logging.disable(logging.CRITICAL)
    from phids.api.schemas.simulation import SimulationConfig
    from phids.engine.loop import SimulationLoop

    scenario = _load(scenario_name)
    loop = SimulationLoop(SimulationConfig.model_validate(scenario), disable_replay=False)

    async def drive() -> int:
        executed = 0
        for _ in range(ticks):
            result = await loop.step()
            executed += 1
            if result.terminated:
                break
        return executed

    executed = asyncio.run(drive())
    root = (
        getattr(loop.replay, "_store_path", None)
        or getattr(loop.replay, "_root_path", None)
        or getattr(loop.replay, "_path", None)
    )
    size = 0
    if root is not None:
        size = sum(f.stat().st_size for f in Path(str(root)).rglob("*") if f.is_file())
    cells = scenario["grid_width"] * scenario["grid_height"]
    layers = scenario["num_signals"] + scenario["num_toxins"] + 2
    raw = executed * cells * layers * 4
    return {"scenario": scenario_name, "ticks": executed, "disk_bytes": size, "raw_float32_bytes": raw}


def _determinism(scenario_name: str, ticks: int) -> dict[str, Any]:
    """Compare telemetry hashes across repeated runs and Numba thread counts."""
    hashes: dict[str, str] = {}
    code = (
        "import json,hashlib,logging,sys;logging.disable(logging.CRITICAL);"
        "from phids.engine.batch.runner import _run_single_headless;"
        f"d=json.load(open({str(EXAMPLES / (scenario_name + '.json'))!r}));"
        f"rows=_run_single_headless(d,{ticks},3);"
        "print(hashlib.sha256(json.dumps(rows,sort_keys=True,default=str).encode()).hexdigest())"
    )
    for threads in (1, 4, 12, 1):
        env = {**os.environ, "NUMBA_NUM_THREADS": str(threads)}
        out = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, check=True)
        hashes[f"threads={threads}#{len(hashes)}"] = out.stdout.strip().splitlines()[-1]
    return {"scenario": scenario_name, "ticks": ticks, "hashes": hashes, "identical": len(set(hashes.values())) == 1}


def run_perf() -> None:
    """Section 8 measurements."""
    result: dict[str, Any] = {"cpu": _cpu_description()}
    scenarios = [
        "wind_tunnel_orchard",
        "eternal_canopy_blueprint",
        "benchmarking_example",
        "ecosystem_equilibrium_benchmark_256x256",
    ]
    result["tick_cost"] = [_spawn_perf(name, 0, 20, 60) for name in scenarios]
    result["thread_scaling"] = [
        _spawn_perf("ecosystem_equilibrium_benchmark_256x256", t, 10, 30) for t in (1, 2, 4, 6, 12)
    ]
    result["wrap_microbenchmark_ns_per_op"] = _microbench_wrap()
    result["replay"] = _replay_compression("wind_tunnel_orchard", 400)
    det_orchard = _determinism("wind_tunnel_orchard", 400)
    det_canopy = _determinism("eternal_canopy_blueprint", 200)
    det_256 = _determinism("ecosystem_equilibrium_benchmark_256x256", 50)
    result["determinism"] = det_orchard
    result["determinism_grids"] = {
        "64x32_orchard": det_orchard,
        "128x128_canopy": det_canopy,
        "256x256_equilibrium": det_256,
    }
    _save("performance", result)


def _cpu_description() -> dict[str, Any]:
    """Describe the host CPU for reproducibility."""
    info: dict[str, Any] = {"logical_cores": os.cpu_count()}
    try:
        text = Path("/proc/cpuinfo").read_text()
        info["model"] = next(
            line.split(":", 1)[1].strip() for line in text.splitlines() if line.startswith("model name")
        )
    except (OSError, StopIteration):
        info["model"] = "unknown"
    return info


def main() -> None:
    """Dispatch the requested experiment."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "command", choices=["dynamics", "priming", "ablation", "crossover", "sobol", "perf", "all", "perf-worker"]
    )
    parser.add_argument("extra", nargs="*")
    args = parser.parse_args()
    if args.command == "perf-worker":
        _perf_worker(args.extra[0], int(args.extra[1]), int(args.extra[2]))
        return
    table = {
        "dynamics": run_dynamics,
        "priming": run_priming,
        "ablation": run_ablation,
        "crossover": run_crossover,
        "sobol": run_sobol,
        "perf": run_perf,
    }
    for name in table if args.command == "all" else [args.command]:
        t0 = time.perf_counter()
        table[name]()
        print(f"[{name}] {time.perf_counter() - t0:.1f}s")


if __name__ == "__main__":
    main()
