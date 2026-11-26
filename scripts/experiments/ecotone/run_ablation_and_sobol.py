# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Ablation, upwind CMN crossover, CRN Sobol GSA, and Theorem 1/2 parity suite.

Executes the empirical verification experiments on the locked Trial #2 ecotone
configuration (``riparian_meadow_ecotone_256x256.json`` and its ``128x64`` twin)
and exports structured JSON and CSV tables under ``results/``.

Sub-commands: ``crossover``, ``theorems``, ``ablation``, ``sobol``, ``all-fast``.
"""

from __future__ import annotations

import argparse
import asyncio
import concurrent.futures
import copy
import csv
import json
import math
import multiprocessing as mp
import os
import random
import time
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
from scipy.stats import qmc  # type: ignore[import-untyped]

REPO_ROOT = Path(__file__).resolve().parents[3]
SCENARIO_DIR = REPO_ROOT / "examples" / "scenarios"
SCENARIO_256 = SCENARIO_DIR / "riparian_meadow_ecotone_256x256.json"
SCENARIO_128 = SCENARIO_DIR / "riparian_meadow_ecotone_128x64_twin.json"
RESULTS_DIR = REPO_ROOT / "docs" / "latex" / "scientific_report" / "data" / "ecotone_256x256" / "results"

WIND_ANGLE_RAD = math.radians(22.5)
N_FLORA = 6
N_HERB = 5


def _load_json(path: Path) -> dict[str, Any]:
    return dict(json.loads(path.read_text(encoding="utf-8")))


def _save_json(name: str, payload: Any) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULTS_DIR / f"{name}.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out


def _save_csv(name: str, rows: list[dict[str, Any]]) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULTS_DIR / f"{name}.csv"
    if not rows:
        out.write_text("", encoding="utf-8")
        return out
    fieldnames = list(rows[0].keys())
    with out.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return out


def _shannon_j(counts: list[int]) -> float:
    total = sum(counts)
    if total <= 0 or len(counts) < 2:
        return 0.0
    h = -sum((c / total) * math.log(c / total) for c in counts if c > 0)
    return h / math.log(len(counts))


def _set_wind(cfg: dict[str, Any], speed: float) -> None:
    cfg["wind_x"] = round(speed * math.cos(WIND_ANGLE_RAD), 6)
    cfg["wind_y"] = round(speed * math.sin(WIND_ANGLE_RAD), 6)


# ---------------------------------------------------------------------------
# 1. Deterministic Upwind CMN Relay Crossover Harness
# ---------------------------------------------------------------------------


def _crossover_case(wind_x: float, regime: str) -> dict[str, Any]:
    """Run a 20-tick cardinal 7-plant relay line under headwind ``wind_x``."""
    from phids.api.schemas.simulation import SimulationConfig
    from phids.engine.components.plant import PlantComponent
    from phids.engine.components.substances import SubstanceComponent
    from phids.engine.loop import SimulationLoop

    random.seed(0)
    np.random.seed(0)

    is_p5_ctrl = regime == "p5_non_cmn_control"
    cmn_on = regime == "p2_p3_cmn_intact"
    flora_id = 1 if is_p5_ctrl else 0

    # Alternating p2 / p3 along cardinal x in [29, 35] or isolated non-CMN p5 control
    if is_p5_ctrl:
        plants = [{"species_id": 1, "x": x, "y": 16, "energy": 35.0} for x in range(29, 36)]
    else:
        plants = [{"species_id": 0 if x == 32 else (x % 2), "x": x, "y": 16, "energy": 55.0} for x in range(29, 36)]

    # Use locked Trial #2 transport scalars (emit=0.55, decay=0.82, v_cmn=2, s2 synth=1 for clean relay timing)
    relay_trig = [
        {
            "aftereffect_ticks": 20,
            "activation_condition": {
                "kind": "herbivore_presence",
                "herbivore_species_id": 0,
                "min_herbivore_population": 1,
            },
            "action": {
                "type": "synthesize_substance",
                "substance_id": 2,
                "synthesis_duration": 1,
                "is_toxin": False,
                "lethal": False,
                "lethality_rate": 0.0,
                "repellent": False,
                "repellent_walk_ticks": 0,
                "energy_cost_per_tick": 0.05,
                "irreversible": True,
            },
            "initiator": {
                "type": "herbivore_attack",
                "herbivore_species_id": 0,
                "min_herbivore_population": 1,
            },
        },
        {
            "aftereffect_ticks": 20,
            "activation_condition": None,
            "action": {
                "type": "synthesize_substance",
                "substance_id": 2,
                "synthesis_duration": 1,
                "is_toxin": False,
                "lethal": False,
                "lethality_rate": 0.0,
                "repellent": False,
                "repellent_walk_ticks": 0,
                "energy_cost_per_tick": 0.05,
                "irreversible": True,
            },
            "initiator": {
                "type": "environmental_signal",
                "signal_id": 2,
                "min_concentration": 0.01,
                "response_curve": "step",
                "hill_cooperativity": 2.0,
                "half_saturation": 0.05,
            },
        },
    ]

    cfg_dict: dict[str, Any] = {
        "grid_width": 64,
        "grid_height": 32,
        "max_ticks": 25,
        "tick_rate_hz": 10.0,
        "num_signals": 3,
        "num_toxins": 1,
        "wind_x": wind_x,
        "wind_y": 0.0,
        "substance_emit_rate": 0.55,
        "signal_decay_factor": 0.82,
        "mycorrhizal_inter_species": cmn_on,
        "mycorrhizal_connection_cost": 0.5 if cmn_on else 1000.0,
        "mycorrhizal_growth_interval_ticks": 1 if cmn_on else 256,
        "mycorrhizal_signal_velocity": 2,
        "flora_species": [
            {
                "species_id": 0,
                "name": "Trifolium_p2" if not is_p5_ctrl else "Unused",
                "base_energy": 55.0,
                "max_energy": 105.0,
                "growth_rate": 0.0,
                "survival_threshold": 5.0,
                "reproduction_interval": 9999,
                "seed_min_dist": 1.0,
                "seed_max_dist": 2.0,
                "seed_energy_cost": 40.0,
                "camouflage": False,
                "camouflage_factor": 1.0,
                "mycorrhizal_tax_per_link": 0.5 if cmn_on else 0.0,
                "triggers": relay_trig,
            },
            {
                "species_id": 1,
                "name": "Brassica_p5_ctrl" if is_p5_ctrl else "Lolium_p3",
                "base_energy": 35.0 if is_p5_ctrl else 55.0,
                "max_energy": 105.0,
                "growth_rate": 0.0,
                "survival_threshold": 5.0,
                "reproduction_interval": 9999,
                "seed_min_dist": 1.0,
                "seed_max_dist": 2.0,
                "seed_energy_cost": 20.0,
                "camouflage": False,
                "camouflage_factor": 1.0,
                "mycorrhizal_tax_per_link": 0.0 if is_p5_ctrl else (0.5 if cmn_on else 0.0),
                "triggers": relay_trig,
            },
        ],
        "herbivore_species": [
            {
                "species_id": 0,
                "name": "Noctua_focal",
                "energy_min": 1.1,
                "velocity": 1,
                "consumption_rate": 0.001,
                "handling_time": 0.1,
                "energy_upkeep_per_individual": 0.0,
                "reproduction_energy_divisor": 100.0,
                "split_population_threshold": 1000,
            }
        ],
        "diet_matrix": {"rows": [[True, True]]},
        "initial_plants": plants,
        "initial_swarms": [{"species_id": 0, "x": 32, "y": 16, "population": 2, "energy": 20.0}],
    }
    _ = flora_id
    loop = SimulationLoop(SimulationConfig.model_validate(cfg_dict), disable_replay=True)

    hop_first_tick: dict[str, int | None] = {f"x{x}": None for x in (29, 30, 31, 33, 34, 35)}
    peak_c_up3 = 0.0
    peak_c_up1 = 0.0
    peak_c_dn3 = 0.0
    cmn_links_end = 0

    async def _drive() -> None:
        nonlocal peak_c_up3, peak_c_up1, peak_c_dn3, cmn_links_end
        for tick in range(20):
            await loop.step()
            peak_c_up3 = max(peak_c_up3, float(loop.env.signal_layers[2, 29, 16]))
            peak_c_up1 = max(peak_c_up1, float(loop.env.signal_layers[2, 31, 16]))
            peak_c_dn3 = max(peak_c_dn3, float(loop.env.signal_layers[2, 35, 16]))
            active_x: set[int] = set()
            for ent in loop.world.query(SubstanceComponent):
                sub = ent.get_component(SubstanceComponent)
                if sub.active and sub.substance_id == 2:
                    owner = loop.world.get_entity(sub.owner_plant_id)
                    if owner is not None:
                        pc = owner.get_component(PlantComponent)
                        active_x.add(pc.x)
            for x in (29, 30, 31, 33, 34, 35):
                if x in active_x and hop_first_tick[f"x{x}"] is None:
                    hop_first_tick[f"x{x}"] = tick
        cmn_links_end = (
            sum(len(e.get_component(PlantComponent).mycorrhizal_connections) for e in loop.world.query(PlantComponent))
            // 2
        )

    asyncio.run(_drive())
    return {
        "wind_x": wind_x,
        "regime": regime,
        "up_1hop_tick": hop_first_tick["x31"],
        "up_2hop_tick": hop_first_tick["x30"],
        "up_3hop_tick": hop_first_tick["x29"],
        "dn_1hop_tick": hop_first_tick["x33"],
        "dn_2hop_tick": hop_first_tick["x34"],
        "dn_3hop_tick": hop_first_tick["x35"],
        "peak_s2_up3": round(peak_c_up3, 6),
        "peak_s2_up1": round(peak_c_up1, 6),
        "peak_s2_dn3": round(peak_c_dn3, 6),
        "cmn_links_end": cmn_links_end,
    }


def cmd_crossover(_args: argparse.Namespace) -> None:
    """Execute the deterministic 20-tick upwind CMN relay crossover harness."""
    winds = [0.0, 0.50, 0.95, 1.00, 1.08, 1.25, 2.00]
    regimes = ["p2_p3_cmn_intact", "p2_p3_cmn_severed", "p5_non_cmn_control"]
    rows = [_crossover_case(w, reg) for w in winds for reg in regimes]
    _save_json("crossover_relay", {"winds": winds, "regimes": regimes, "rows": rows})
    _save_csv("crossover_relay", rows)
    print("CROSSOVER_DONE rows=", len(rows))
    for r in rows:
        up_str = f"{r['up_1hop_tick']}/{r['up_2hop_tick']}/{r['up_3hop_tick']}"
        print(
            f"  u={r['wind_x']:4.2f} {r['regime']:20s} up(1/2/3)={up_str} "
            f"dn3={r['dn_3hop_tick']} peak_up3={r['peak_s2_up3']:.5f} "
            f"peak_dn3={r['peak_s2_dn3']:.5f} links={r['cmn_links_end']}"
        )


# ---------------------------------------------------------------------------
# 2. Theorem 1 & Theorem 2 Paper-Code Parity Sync (Trial #2)
# ---------------------------------------------------------------------------


def _theta_crit(e0: float, e_min: float, a_eff: float, t_h: float, n_swarm: int) -> float:
    return (1.0 / float(n_swarm)) * ((1.0 / a_eff) * math.log(e0 / e_min) + t_h * (e0 - e_min))


def _continuous_grazing_probe(
    e0: float,
    e_min: float,
    c_rate: float,
    t_h: float,
    velocity: int,
    n_swarm: int,
    theta: int,
    horizon: int = 24,
) -> dict[str, Any]:
    """Run an hourly (stride=1) continuous-grazing verification in SimulationLoop."""
    from phids.api.schemas.simulation import SimulationConfig
    from phids.engine.components.plant import PlantComponent
    from phids.engine.components.swarm import SwarmComponent
    from phids.engine.loop import SimulationLoop

    random.seed(0)
    np.random.seed(0)
    cfg_dict: dict[str, Any] = {
        "grid_width": 16,
        "grid_height": 16,
        "max_ticks": horizon + 2,
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
                "name": "Focal",
                "base_energy": e0,
                "max_energy": max(150.0, e0 * 2.0),
                "growth_rate": 0.0,
                "survival_threshold": e_min,
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
                "name": "Grazer",
                "energy_min": 5.0,
                "velocity": velocity,
                "consumption_rate": c_rate,
                "handling_time": t_h,
                "energy_upkeep_per_individual": 0.0,
                "reproduction_energy_divisor": 1e6,
                "split_population_threshold": 10000,
            }
        ],
        "diet_matrix": {"rows": [[True]]},
        "initial_plants": [{"species_id": 0, "x": 8, "y": 8, "energy": e0}],
        "initial_swarms": [{"species_id": 0, "x": 8, "y": 8, "population": n_swarm, "energy": 5000.0}],
    }
    loop = SimulationLoop(SimulationConfig.model_validate(cfg_dict), disable_replay=True)
    death_tick: int | None = None
    herb_dead_tick: int | None = None
    for t in range(horizon):
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
        if not list(loop.world.query(PlantComponent)) and death_tick is None:
            death_tick = t
        if not list(loop.world.query(SwarmComponent)) and herb_dead_tick is None:
            herb_dead_tick = t
    plants_end = [e.get_component(PlantComponent) for e in loop.world.query(PlantComponent)]
    return {
        "theta_ticks": theta,
        "plant_survived": len(plants_end) > 0,
        "final_plant_energy": round(float(plants_end[0].energy), 4) if plants_end else 0.0,
        "plant_death_tick": death_tick,
        "herb_extinct_tick": herb_dead_tick,
    }


def _hopf_equilibrium(r: float, k_cap: float, a_eff: float, t_h: float, e_eff: float, m_herb: float) -> dict[str, Any]:
    denom = e_eff - m_herb * t_h
    if denom <= 0.0:
        return {"feasible": False, "reason": "m_herb * T_h >= e_eff"}
    e_star = m_herb / (a_eff * denom)
    if e_star >= k_cap:
        return {"feasible": False, "E_star": round(e_star, 4), "K": k_cap, "reason": "E_star >= K"}
    n_star = (r / a_eff) * (1.0 - e_star / k_cap) * (1.0 + a_eff * t_h * e_star)
    denom_sq = (1.0 + a_eff * t_h * e_star) ** 2
    alpha = r * (1.0 - 2.0 * e_star / k_cap) - (a_eff * n_star) / denom_sq
    beta = (a_eff * e_star) / (1.0 + a_eff * t_h * e_star)
    gamma = (e_eff * a_eff * n_star) / denom_sq
    p_val = -alpha
    r_delay = beta * gamma
    if p_val <= 0.0:
        return {
            "feasible": True,
            "E_star": round(e_star, 4),
            "N_star": round(n_star, 4),
            "alpha": round(alpha, 6),
            "hopf_regime": "already_unstable_at_tau0",
            "tau_star": 0.0,
        }
    omega0 = math.sqrt((-p_val * p_val + math.sqrt(p_val**4 + 4.0 * r_delay * r_delay)) / 2.0)
    cos_arg = max(-1.0, min(1.0, (omega0 * omega0) / r_delay))
    tau_star = math.acos(cos_arg) / omega0
    return {
        "feasible": True,
        "E_star": round(e_star, 4),
        "N_star": round(n_star, 4),
        "alpha": round(alpha, 6),
        "beta": round(beta, 6),
        "gamma": round(gamma, 6),
        "omega_0": round(omega0, 6),
        "tau_star": round(tau_star, 6),
        "hopf_regime": "supercritical_at_tau_star",
    }


def cmd_theorems(_args: argparse.Namespace) -> None:
    """Compute exact Theorem 1 & Theorem 2 values on locked Trial #2 and verify in-engine."""
    cfg = _load_json(SCENARIO_256)
    flora = cfg["flora_species"]
    herbs = cfg["herbivore_species"]
    diet = cfg["diet_matrix"]["rows"]

    thm1_rows: list[dict[str, Any]] = []
    thm2_rows: list[dict[str, Any]] = []

    for h in herbs:
        hid = h["species_id"]
        for fl in flora:
            fid = fl["species_id"]
            if not diet[hid][fid]:
                continue
            v_eff = max(1, int(h["velocity"]))
            a_hourly = float(h["consumption_rate"]) / float(v_eff)
            a_diurnal = (float(h["consumption_rate"]) * 24.0) / float(v_eff)
            e0 = float(fl["base_energy"])
            e_min = float(fl["survival_threshold"])
            t_h = float(h["handling_time"])
            n_split = int(h["split_population_threshold"])
            n_ref = 16
            tc_hr_ref = _theta_crit(e0, e_min, a_hourly, t_h, n_ref)
            tc_hr_split = _theta_crit(e0, e_min, a_hourly, t_h, n_split)
            tc_day_ref = _theta_crit(e0, e_min, a_diurnal, t_h, n_ref)

            # Collect primed and unprimed toxin latencies on this host
            tox_durs = sorted(
                {
                    int(tr["action"]["synthesis_duration"])
                    for tr in fl["triggers"]
                    if tr["action"]["type"] == "synthesize_substance" and tr["action"]["is_toxin"]
                }
            )
            thm1_rows.append(
                {
                    "flora": f"p{fid} ({fl['name']})",
                    "herb": f"h{hid} ({h['name']})",
                    "E0": e0,
                    "E_min": e_min,
                    "a_hourly_runtime": round(a_hourly, 4),
                    "a_diurnal_runtime": round(a_diurnal, 4),
                    "T_h": t_h,
                    "toxin_delays": str(tox_durs),
                    "theta_crit_hr_N16": round(tc_hr_ref, 4),
                    "theta_crit_hr_Nsplit": round(tc_hr_split, 4),
                    "theta_crit_diurnal_N16": round(tc_day_ref, 4),
                }
            )

            # Theorem 2 continuous hourly projection
            r_h = (float(fl["growth_rate"]) / 100.0) * e0 / float(fl["max_energy"])
            k_cap = float(fl["max_energy"])
            d_mod = float(fl["passive_defenses"]["digestibility_modifier"])
            d_eff = float(h["resistances"]["digestive_efficiency"])
            e_eff = min(1.0, max(0.0, d_mod * d_eff))
            m_herb = float(h["energy_min"]) * float(h["energy_upkeep_per_individual"])
            hopf = _hopf_equilibrium(r_h, k_cap, a_hourly, t_h, e_eff, m_herb)
            thm2_rows.append(
                {
                    "flora": f"p{fid}",
                    "herb": f"h{hid}",
                    "r_h": round(r_h, 6),
                    "K": k_cap,
                    "a_hourly": round(a_hourly, 4),
                    "T_h": t_h,
                    "e_eff": round(e_eff, 4),
                    "m_herb_h": round(m_herb, 6),
                    **hopf,
                }
            )

    # Continuous-grazing verification harnesses:
    # (a) Analytical reference (Cor. 1: E0=50, Emin=10, a=0.06, Th=0.30, N=25 -> 1.5530 h)
    ref_tc = _theta_crit(50.0, 10.0, 0.06, 0.30, 25)
    ref_sweep = [_continuous_grazing_probe(50.0, 10.0, 0.06, 0.30, 1, 25, th) for th in (1, 2, 3, 4)]

    # (b) Locked Trial #2 p3 (Lolium: E0=55, Emin=11) vs h3 (Noctua: c=1.513921, v=3, Th=0.334232) at N=40
    # a_hourly = 1.513921 / 3 = 0.50464 -> theta_crit(N=40) = (1/40)*(ln(5)/0.50464 + 0.334232*44) = 0.447 h,
    # and at N=5 -> theta_crit = 3.579 h (between primed s8=2 ticks and unprimed s8=10 ticks!)
    p3 = flora[3]
    h3 = herbs[3]
    t2_tc_n5 = _theta_crit(
        p3["base_energy"],
        p3["survival_threshold"],
        h3["consumption_rate"] / h3["velocity"],
        h3["handling_time"],
        5,
    )
    t2_sweep_n5 = [
        _continuous_grazing_probe(
            p3["base_energy"],
            p3["survival_threshold"],
            h3["consumption_rate"],
            h3["handling_time"],
            int(h3["velocity"]),
            5,
            th,
        )
        for th in (2, 3, 4, 10)
    ]

    # (c) Locked Trial #2 p0 (Populus: E0=70, Emin=14) vs h0 (Lymantria: c=3.3337, v=2, Th=0.113987) at N=4
    p0 = flora[0]
    h0 = herbs[0]
    t2_tc_p0 = _theta_crit(
        p0["base_energy"],
        p0["survival_threshold"],
        h0["consumption_rate"] / h0["velocity"],
        h0["handling_time"],
        4,
    )
    t2_sweep_p0 = [
        _continuous_grazing_probe(
            p0["base_energy"],
            p0["survival_threshold"],
            h0["consumption_rate"],
            h0["handling_time"],
            int(h0["velocity"]),
            4,
            th,
        )
        for th in (1, 2, 3, 12)
    ]

    ref_dde = _hopf_equilibrium(0.50, 100.0, 0.05, 0.30, 0.60, 0.50)

    payload = {
        "theorem1_trial2_matrix": thm1_rows,
        "theorem2_trial2_matrix": thm2_rows,
        "theorem2_analytical_reference_dde": ref_dde,
        "harness_cor1_reference": {"theta_crit_h": round(ref_tc, 6), "sweep": ref_sweep},
        "harness_trial2_p3_h3_N5": {"theta_crit_h": round(t2_tc_n5, 6), "sweep": t2_sweep_n5},
        "harness_trial2_p0_h0_N4": {"theta_crit_h": round(t2_tc_p0, 6), "sweep": t2_sweep_p0},
    }
    _save_json("theorem_parity", payload)
    _save_csv("theorem1_trial2_matrix", thm1_rows)
    _save_csv("theorem2_trial2_matrix", thm2_rows)
    print(f"COR1_REF theta_crit={ref_tc:.4f}h sweep={ref_sweep}")
    print(f"TRIAL2_p3_h3_N5 theta_crit={t2_tc_n5:.4f}h sweep={t2_sweep_n5}")
    print(f"TRIAL2_p0_h0_N4 theta_crit={t2_tc_p0:.4f}h sweep={t2_sweep_p0}")
    print("THM2_REF_DDE", ref_dde)
    for r in thm1_rows:
        print(
            "  THM1:", r["flora"], "x", r["herb"], "tc_hr(N16)=", r["theta_crit_hr_N16"], "delays=", r["toxin_delays"]
        )


# ---------------------------------------------------------------------------
# 3. Factorial Biotope Wind & Dual-Channel Ablation (Scenario 3)
# ---------------------------------------------------------------------------


def _ablation_worker(job: tuple[str, float, int, int, str]) -> dict[str, Any]:
    treatment, wind_speed, seed, max_ticks, cache_file_str = job
    cache_path = Path(cache_file_str)
    if cache_path.exists():
        return dict(json.loads(cache_path.read_text(encoding="utf-8")))

    os.environ["NUMBA_NUM_THREADS"] = "1"
    random.seed(seed)
    np.random.seed(seed)

    from phids.api.schemas.simulation import SimulationConfig
    from phids.engine.loop import SimulationLoop
    from phids.engine.systems.interaction import feeding as sys_feed

    cfg_dict = _load_json(SCENARIO_256)
    _set_wind(cfg_dict, wind_speed)
    if treatment in ("cmn_severed", "fully_ablated"):
        cfg_dict["mycorrhizal_connection_cost"] = 1_000_000.0
        cfg_dict["mycorrhizal_growth_interval_ticks"] = 256
    if treatment == "fully_ablated":
        for sp in cfg_dict["flora_species"]:
            sp["triggers"] = []

    cfg = SimulationConfig.model_validate(cfg_dict)
    cfg.max_ticks = max_ticks + 1
    loop = SimulationLoop(cfg, disable_replay=True)

    killed_by_flora: Counter[int] = Counter()
    orig_feed = sys_feed._feed_on_single_plant

    def wrapped_feed(swarm: Any, target_plant: Any, *f_args: Any, **f_kwargs: Any) -> Any:
        pre_sp = int(target_plant.species_id)
        metab, killed = orig_feed(swarm, target_plant, *f_args, **f_kwargs)
        if killed:
            killed_by_flora[pre_sp] += 1
        return metab, killed

    sys_feed._feed_on_single_plant = wrapped_feed

    t0 = time.perf_counter()

    async def _run() -> None:
        for _ in range(max_ticks):
            res = await loop.step()
            if res.terminated:
                break

    asyncio.run(_run())
    elapsed = round(time.perf_counter() - t0, 2)

    rows = loop.telemetry._rows
    half = len(rows) // 2
    mean_reserve_tail = float(np.mean([float(r["total_flora_energy"]) for r in rows[half:]])) if rows else 0.0
    late_herb_mean = float(np.mean([float(r["herbivore_population"]) for r in rows[half:]])) if rows else 0.0
    tot_herb_deaths = int(sum(float(r.get("death_herbivore_feeding", 0.0)) for r in rows))
    tot_def_deaths = int(sum(float(r.get("death_defense_maintenance", 0.0)) for r in rows))
    tot_myc_deaths = int(sum(float(r.get("death_mycorrhiza", 0.0)) for r in rows))

    last = rows[-1] if rows else {}
    p_map = {int(k): int(v) for k, v in dict(last.get("plant_pop_by_species", {}) or {}).items()}
    h_map = {int(k): int(v) for k, v in dict(last.get("swarm_pop_by_species", {}) or {}).items()}
    plants_end = [p_map.get(i, 0) for i in range(N_FLORA)]
    heads_end = [h_map.get(i, 0) for i in range(N_HERB)]

    out = {
        "treatment": treatment,
        "wind_speed": wind_speed,
        "seed": seed,
        "ticks": len(rows),
        "elapsed_s": elapsed,
        "killed_by_flora": [killed_by_flora.get(i, 0) for i in range(N_FLORA)],
        "death_herbivory_total": tot_herb_deaths,
        "death_defense_total": tot_def_deaths,
        "death_mycorrhiza_total": tot_myc_deaths,
        "mean_flora_energy_tail": round(mean_reserve_tail, 2),
        "mean_herb_heads_tail": round(late_herb_mean, 2),
        "final_plants": plants_end,
        "final_heads": heads_end,
        "final_flora_total": sum(plants_end),
        "final_herb_total": sum(heads_end),
        "final_j_flora": round(_shannon_j(plants_end), 4),
        "final_j_herb": round(_shannon_j(heads_end), 4),
    }
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(out), encoding="utf-8")
    return out


def cmd_ablation(args: argparse.Namespace) -> None:
    """Run factorial wind x signalling-treatment ablation across seeds."""
    winds = [0.0, 0.50, 0.95, 1.25, 2.00]
    treatments = ["intact", "cmn_severed", "fully_ablated"]
    seeds = list(range(args.seeds))
    cache_dir = RESULTS_DIR / "ablation_cache"
    jobs = [
        (tr, w, s, args.max_ticks, str(cache_dir / f"{tr}_u{w:.2f}_s{s}_t{args.max_ticks}.json"))
        for w in winds
        for tr in treatments
        for s in seeds
    ]
    t0 = time.perf_counter()
    results: list[dict[str, Any]] = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers, mp_context=mp.get_context("spawn")) as ex:
        for idx, res in enumerate(ex.map(_ablation_worker, jobs), start=1):
            results.append(res)
            if idx % 10 == 0 or idx == len(jobs):
                print(
                    f"ABLATION_PROGRESS {idx}/{len(jobs)} ({res['treatment']} u={res['wind_speed']} s={res['seed']} "
                    f"t={res['elapsed_s']}s total_elapsed={time.perf_counter() - t0:.1f}s)",
                    flush=True,
                )

    summary_rows: list[dict[str, Any]] = []
    for w in winds:
        for tr in treatments:
            grp = [r for r in results if r["wind_speed"] == w and r["treatment"] == tr]
            n = max(1, len(grp))
            row: dict[str, Any] = {
                "wind_speed": w,
                "treatment": tr,
                "n_runs": len(grp),
                "herb_deaths_mean": round(float(np.mean([r["death_herbivory_total"] for r in grp])), 2),
                "herb_deaths_se": round(
                    float(np.std([r["death_herbivory_total"] for r in grp], ddof=1) / math.sqrt(n)), 2
                )
                if n > 1
                else 0.0,
                "herb_heads_tail_mean": round(float(np.mean([r["mean_herb_heads_tail"] for r in grp])), 2),
                "herb_heads_end_mean": round(float(np.mean([r["final_herb_total"] for r in grp])), 2),
                "flora_energy_tail_mean": round(float(np.mean([r["mean_flora_energy_tail"] for r in grp])), 2),
                "j_flora_mean": round(float(np.mean([r["final_j_flora"] for r in grp])), 4),
                "j_herb_mean": round(float(np.mean([r["final_j_herb"] for r in grp])), 4),
            }
            for sp in range(N_FLORA):
                vals = [r["killed_by_flora"][sp] for r in grp]
                row[f"killed_p{sp}_mean"] = round(float(np.mean(vals)), 2)
            summary_rows.append(row)

    _save_json("ablation_256x256_summary", {"max_ticks": args.max_ticks, "summary": summary_rows, "runs": results})
    _save_csv("ablation_256x256", summary_rows)
    print(f"ABLATION_DONE total_s={time.perf_counter() - t0:.1f}")
    for row in summary_rows:
        print(row)


# ---------------------------------------------------------------------------
# 4. Converged CRN Variance-Based Sobol GSA (Scenario 4)
# ---------------------------------------------------------------------------

SOBOL_FACTORS = [
    ("consumption_rate_mult", 0.8, 1.4),
    ("energy_min_mult", 0.7, 1.3),
    ("defense_cmn_cost_mult", 0.5, 1.5),
    ("wind_magnitude", 0.0, 2.0),
    ("p4_camo_repellent_strength", 0.2, 1.0),
]


def _apply_sobol_theta(base: dict[str, Any], theta: list[float]) -> dict[str, Any]:
    cfg = copy.deepcopy(base)
    c_mult, e_mult, cost_mult, wind_mag, p4_strength = theta
    for h in cfg["herbivore_species"]:
        h["consumption_rate"] = round(h["consumption_rate"] * c_mult, 6)
        h["energy_min"] = round(h["energy_min"] * e_mult, 6)
    cfg["mycorrhizal_connection_cost"] = round(cfg["mycorrhizal_connection_cost"] * cost_mult, 6)
    for sp in cfg["flora_species"]:
        sp["mycorrhizal_tax_per_link"] = round(sp["mycorrhizal_tax_per_link"] * cost_mult, 6)
        if sp["species_id"] == 4:
            # Strength in [0.2, 1.0]: lowers camouflage_factor (0.85 -> 0.25) and increases walk ticks (2 -> 8)
            sp["camouflage_factor"] = round(1.0 - 0.75 * p4_strength, 6)
        for tr in sp["triggers"]:
            act = tr["action"]
            if act["type"] == "synthesize_substance":
                act["energy_cost_per_tick"] = round(act["energy_cost_per_tick"] * cost_mult, 6)
                if sp["species_id"] == 4 and act["substance_id"] == 5:
                    act["repellent_walk_ticks"] = max(1, round(8.0 * p4_strength))
    _set_wind(cfg, wind_mag)
    return cfg


def _sobol_worker(job: tuple[int, str, list[float], int, int]) -> dict[str, Any]:
    idx, scen_str, theta, max_ticks, crn_seed = job
    os.environ["NUMBA_NUM_THREADS"] = "1"
    random.seed(crn_seed)
    np.random.seed(crn_seed)

    from phids.api.schemas.simulation import SimulationConfig
    from phids.engine.loop import SimulationLoop

    cfg_dict = _apply_sobol_theta(_load_json(Path(scen_str)), theta)
    cfg = SimulationConfig.model_validate(cfg_dict)
    cfg.max_ticks = max_ticks + 1
    loop = SimulationLoop(cfg, disable_replay=True)

    t0 = time.perf_counter()

    async def _run() -> None:
        for _ in range(max_ticks):
            res = await loop.step()
            if res.terminated:
                break

    asyncio.run(_run())
    rows = loop.telemetry._rows
    half = len(rows) // 2
    mean_reserve = float(np.mean([float(r["total_flora_energy"]) for r in rows[half:]])) if rows else 0.0
    last = rows[-1] if rows else {}
    p_map = {int(k): int(v) for k, v in dict(last.get("plant_pop_by_species", {}) or {}).items()}
    plants_end = [p_map.get(i, 0) for i in range(N_FLORA)]
    herb_end = int(last.get("herbivore_population", 0))
    return {
        "idx": idx,
        "elapsed_s": round(time.perf_counter() - t0, 2),
        "ticks": len(rows),
        "mean_flora_reserve": round(mean_reserve, 4),
        "terminal_j_flora": round(_shannon_j(plants_end), 6),
        "terminal_herb_heads": herb_end,
    }


def _sobol_indices(f_a: np.ndarray, f_b: np.ndarray, f_ab: np.ndarray, rng: np.random.Generator) -> dict[str, Any]:
    """Compute Saltelli S1 and Jansen ST with 500-replicate 95% bootstrap CIs."""
    n, _d = f_ab.shape

    def est(idx: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        a, b, ab = f_a[idx], f_b[idx], f_ab[idx]
        ab_pool = np.concatenate([a, b])
        mu = float(np.mean(ab_pool))
        var = float(np.var(ab_pool, ddof=1))
        if var <= 1e-18:
            zeros = np.zeros(ab.shape[1], dtype=np.float64)
            return zeros, zeros
        s1 = np.mean((b - mu)[:, None] * (ab - a[:, None]), axis=0) / var
        st = 0.5 * np.mean((a[:, None] - ab) ** 2, axis=0) / var
        return s1, st

    s1, st = est(np.arange(n))
    boots = [est(rng.integers(0, n, size=(n,))) for _ in range(500)]
    s1_ci = np.percentile([b[0] for b in boots], [2.5, 97.5], axis=0)
    st_ci = np.percentile([b[1] for b in boots], [2.5, 97.5], axis=0)
    return {
        "S1": [round(float(x), 5) for x in s1],
        "ST": [round(float(x), 5) for x in st],
        "S1_ci_low": [round(float(x), 5) for x in s1_ci[0]],
        "S1_ci_high": [round(float(x), 5) for x in s1_ci[1]],
        "ST_ci_low": [round(float(x), 5) for x in st_ci[0]],
        "ST_ci_high": [round(float(x), 5) for x in st_ci[1]],
    }


def cmd_sobol(args: argparse.Namespace) -> None:
    """Run CRN Sobol GSA on 128x64 (or 256x256 cross-check) with checkpoint cache."""
    scen_path = SCENARIO_256 if args.grid == "256x256" else SCENARIO_128
    d = len(SOBOL_FACTORS)
    n_base = args.n_base
    sample = qmc.Sobol(d=2 * d, scramble=True, seed=7).random(n_base)
    lo = np.array([f[1] for f in SOBOL_FACTORS])
    hi = np.array([f[2] for f in SOBOL_FACTORS])
    mat_a = lo + sample[:, :d] * (hi - lo)
    mat_b = lo + sample[:, d:] * (hi - lo)
    blocks = [mat_a, mat_b] + [np.where(np.arange(d) == i, mat_b, mat_a) for i in range(d)]
    thetas = [row.tolist() for blk in blocks for row in blk]

    cache_path = RESULTS_DIR / f"sobol_{args.grid}_n{n_base}_t{args.max_ticks}_cache.jsonl"
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    cached: dict[int, dict[str, Any]] = {}
    if cache_path.exists():
        for ln in cache_path.read_text(encoding="utf-8").splitlines():
            if ln.strip():
                rec = json.loads(ln)
                cached[int(rec["idx"])] = rec

    pending = [(i, str(scen_path), th, args.max_ticks, args.crn_seed) for i, th in enumerate(thetas) if i not in cached]
    print(
        f"SOBOL_START grid={args.grid} n_base={n_base} total={len(thetas)} cached={len(cached)} pending={len(pending)}",
        flush=True,
    )
    t0 = time.perf_counter()
    if pending:
        with cache_path.open("a", encoding="utf-8") as fp:
            with concurrent.futures.ProcessPoolExecutor(
                max_workers=args.workers, mp_context=mp.get_context("spawn")
            ) as ex:
                for done_cnt, res in enumerate(ex.map(_sobol_worker, pending, chunksize=2), start=1):
                    cached[int(res["idx"])] = res
                    fp.write(json.dumps(res) + "\n")
                    if done_cnt % 50 == 0 or done_cnt == len(pending):
                        fp.flush()
                        print(
                            f"SOBOL_PROGRESS {len(cached)}/{len(thetas)} elapsed={time.perf_counter() - t0:.1f}s",
                            flush=True,
                        )

    ordered = [cached[i] for i in range(len(thetas))]
    rng = np.random.default_rng(11)
    outputs: dict[str, Any] = {}
    csv_rows: list[dict[str, Any]] = []
    for metric in ("mean_flora_reserve", "terminal_j_flora", "terminal_herb_heads"):
        y = np.array([float(r[metric]) for r in ordered], dtype=np.float64)
        f_a, f_b = y[:n_base], y[n_base : 2 * n_base]
        f_ab = np.stack([y[(2 + i) * n_base : (3 + i) * n_base] for i in range(d)], axis=1)
        idx_res = _sobol_indices(f_a, f_b, f_ab, rng)
        idx_res["mean"] = round(float(np.mean(y)), 4)
        idx_res["sd"] = round(float(np.std(y, ddof=1)), 4)
        outputs[metric] = idx_res
        for fi, (fname, flo, fhi) in enumerate(SOBOL_FACTORS):
            csv_rows.append(
                {
                    "metric": metric,
                    "factor": fname,
                    "range": f"[{flo}, {fhi}]",
                    "S1": idx_res["S1"][fi],
                    "S1_ci_low": idx_res["S1_ci_low"][fi],
                    "S1_ci_high": idx_res["S1_ci_high"][fi],
                    "ST": idx_res["ST"][fi],
                    "ST_ci_low": idx_res["ST_ci_low"][fi],
                    "ST_ci_high": idx_res["ST_ci_high"][fi],
                }
            )

    stem = f"sobol_{args.grid}_n{n_base}_t{args.max_ticks}"
    _save_json(
        stem,
        {
            "grid": args.grid,
            "n_base": n_base,
            "total_runs": len(thetas),
            "crn_seed": args.crn_seed,
            "factors": SOBOL_FACTORS,
            "outputs": outputs,
        },
    )
    _save_csv(stem, csv_rows)
    print(f"SOBOL_DONE {stem} wall_s={time.perf_counter() - t0:.1f}")
    for metric, od in outputs.items():
        print(
            f"  METRIC={metric} mean={od['mean']} sd={od['sd']} sum_S1={sum(od['S1']):.4f} sum_ST={sum(od['ST']):.4f}"
        )
        for fi, (fname, _, _) in enumerate(SOBOL_FACTORS):
            s1_ci = f"[{od['S1_ci_low'][fi]:+.4f}, {od['S1_ci_high'][fi]:+.4f}]"
            st_ci = f"[{od['ST_ci_low'][fi]:.4f}, {od['ST_ci_high'][fi]:.4f}]"
            print(f"    {fname:28s}: S1={od['S1'][fi]:+.4f} {s1_ci}  ST={od['ST'][fi]:.4f} {st_ci}")


def main() -> None:
    """Parse CLI arguments and dispatch the requested experiment."""
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("crossover")
    p.set_defaults(fn=cmd_crossover)

    p = sub.add_parser("theorems")
    p.set_defaults(fn=cmd_theorems)

    p = sub.add_parser("ablation")
    p.add_argument("--seeds", type=int, default=6)
    p.add_argument("--max-ticks", type=int, default=2500)
    p.add_argument("--workers", type=int, default=10)
    p.set_defaults(fn=cmd_ablation)

    p = sub.add_parser("sobol")
    p.add_argument("--grid", choices=("128x64", "256x256"), default="128x64")
    p.add_argument("--n-base", type=int, default=256)
    p.add_argument("--max-ticks", type=int, default=1500)
    p.add_argument("--workers", type=int, default=10)
    p.add_argument("--crn-seed", type=int, default=42)
    p.set_defaults(fn=cmd_sobol)

    args = parser.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
