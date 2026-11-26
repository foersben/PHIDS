# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Standalone Optuna TPE + ASHA tuner for the riparian-meadow ecotone scenario.

The tuner searches a compact 10-dimensional multiplier space around the hand-calibrated
baseline of ``build_ecotone_scenario.py`` on the 128 x 64 twin, targeting a bounded,
quasi-periodic Lotka-Volterra regime (all six flora and five herbivore guilds persist
inside stable envelopes instead of saturating the grid).

Design notes:

* Sampler: ``TPESampler(multivariate=True, constant_liar=True)`` - each worker uses
  ``seed = 42 + worker_index`` because identical seeds would replay identical start-up
  samples across workers sharing one journal.
* Pruner: ``SuccessiveHalvingPruner(min_resource=400, reduction_factor=3)`` evaluated at
  the ticks 400 / 1200 / 2400 / 4000. Hard-rule violations raise ``TrialPruned`` directly.
* Tuning uses a fixed simulation seed (``TUNE_SEED``) that is disjoint from the validation
  seeds (0, 1, 2), so the validation gate is a genuine held-out test of persistence.
* Storage: ``JournalFileBackend`` (multi-process safe, no SQLite lock contention).
* The repository tuner ``src/phids/analytics/tuning.py`` is deliberately not touched.

Sub-commands: ``smoke``, ``tune``, ``status``, ``validate``, ``export``, ``confirm``.
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import json
import math
import multiprocessing as mp
import os
import random
import statistics
import sys
import time
import traceback
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import optuna
from optuna.storages import JournalStorage
from optuna.storages.journal import JournalFileBackend
from optuna.study import MaxTrialsCallback
from optuna.trial import TrialState

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.experiments.ecotone import build_ecotone_scenario as scen  # noqa: E402

DATA_DIR = REPO_ROOT / "docs" / "latex" / "scientific_report" / "data" / "ecotone_256x256"
OUT_DIR = DATA_DIR / "optuna_runs"
SCENARIO_DIR = REPO_ROOT / "examples" / "scenarios"
DEFAULT_STUDY = "ecotone_128x64_v1"

TUNE_SEED = 7
VALIDATION_SEEDS = (0, 1, 2)
MAX_TICKS = 4000
SAMPLE_EVERY = 50
CHECKPOINTS = (400, 1200, 2400, 4000)
CASCADE_SPAN = 1000
N_FLORA = 6
N_HERB = 5
N_SUB = 9
N_CASCADE_CHANNELS = N_SUB + 3

SEARCH_SPACE: dict[str, tuple[float, float]] = {
    "repro_interval_scale": (1.2, 2.6),
    "seed_cost_scale": (1.0, 1.4),
    "p1_growth_scale": (1.0, 1.6),
    "h0_vigor": (0.8, 1.8),
    "h1_vigor": (0.5, 1.2),
    "h2_vigor": (0.6, 1.5),
    "h3_vigor": (0.6, 1.8),
    "h4_vigor": (0.6, 1.8),
    "woody_toxin_scale": (0.7, 1.4),
    "meadow_toxin_scale": (0.4, 1.1),
}

BASELINE: dict[str, float] = {
    "repro_interval_scale": 1.2,
    "seed_cost_scale": 1.0,
    "p1_growth_scale": 1.0,
    "h0_vigor": 1.0,
    "h1_vigor": 1.0,
    "h2_vigor": 1.0,
    "h3_vigor": 1.0,
    "h4_vigor": 1.0,
    "woody_toxin_scale": 1.0,
    "meadow_toxin_scale": 1.0,
}

WEIGHTS: dict[str, float] = {
    "occupancy": 0.30,
    "flora_j": 0.10,
    "herb_j": 0.15,
    "cv": 0.20,
    "cascade": 0.15,
    "headcount": 0.10,
}


# ---------------------------------------------------------------------------
# Scenario construction
# ---------------------------------------------------------------------------


def base_config_dict(width: int, height: int) -> dict[str, Any]:
    """Return the validated baseline scenario as a JSON-compatible dictionary."""
    cfg, _ = scen.build_config(width, height, seed=42)
    return dict(json.loads(json.dumps(cfg.model_dump(mode="json"))))


def apply_params(cfg: dict[str, Any], p: dict[str, float]) -> dict[str, Any]:
    """Apply the tuning multipliers to a scenario dictionary and return a modified copy.

    Vigour ``v`` of a guild scales ``consumption_rate`` by ``v``, divides ``handling_time`` by ``v``
    (so the Holling II ceiling ``1/h`` also scales by ``v``) and scales basal upkeep by ``sqrt(v)``.
    Seed costs are clamped to ``base_energy - survival_threshold`` so that a freshly germinated
    plant can always afford to reproduce.
    """
    out = copy.deepcopy(cfg)
    woody = p["woody_toxin_scale"]
    meadow = p["meadow_toxin_scale"]
    for sp in out["flora_species"]:
        sp["reproduction_interval"] = max(1, round(sp["reproduction_interval"] * p["repro_interval_scale"]))
        ceiling = sp["base_energy"] - sp["survival_threshold"]
        sp["seed_energy_cost"] = round(min(sp["seed_energy_cost"] * p["seed_cost_scale"], ceiling), 4)
        if sp["species_id"] == 1:
            sp["growth_rate"] = round(sp["growth_rate"] * p["p1_growth_scale"], 6)
        for trig in sp["triggers"]:
            act = trig["action"]
            if act["type"] != "synthesize_substance":
                continue
            sub = act["substance_id"]
            if sub == 4:
                act["lethality_rate"] = round(act["lethality_rate"] * woody, 6)
            elif sub == 3:
                act["repellent_walk_ticks"] = max(1, round(act["repellent_walk_ticks"] * woody))
            elif sub in (6, 7, 8):
                act["lethality_rate"] = round(act["lethality_rate"] * meadow, 6)
    for h in out["herbivore_species"]:
        v = p[f"h{h['species_id']}_vigor"]
        h["consumption_rate"] = round(h["consumption_rate"] * v, 6)
        h["handling_time"] = round(h["handling_time"] / v, 6)
        h["energy_upkeep_per_individual"] = round(h["energy_upkeep_per_individual"] * math.sqrt(v), 6)
    return out


def tuned_config_dict(width: int, height: int, p: dict[str, float]) -> dict[str, Any]:
    """Build the tuned scenario dictionary for an arbitrary grid size."""
    return apply_params(base_config_dict(width, height), p)


# ---------------------------------------------------------------------------
# Cascade probe (process-global activation counters)
# ---------------------------------------------------------------------------

_SUB_ACT: Counter[int] = Counter()
_WITHDRAW: Counter[int] = Counter()
_PROBE_STATE = {"installed": False}


def _install_probe() -> None:
    """Wrap the signalling hooks once per process so that activations and withdrawals are counted."""
    if _PROBE_STATE["installed"]:
        return
    from phids.api.schemas.triggers import ResourceWithdrawalAction
    from phids.engine.systems.signaling import synthesis, triggers

    orig_action = triggers._process_single_trigger_action
    orig_adv = synthesis._process_advance_single_synthesis

    def action_probe(
        trig: Any, plant: Any, world: Any, env: Any, owner: Any, swarm_pop: Any, active: Any, entities: Any
    ) -> Any:
        if isinstance(trig.schema.action, ResourceWithdrawalAction):
            check_activation = triggers._check_activation_condition  # type: ignore[attr-defined]
            gate_open = trig.schema.activation_condition is None or check_activation(
                plant, plant.entity_id, trig.activation_condition_dump, env, swarm_pop, active
            )
            if gate_open:
                _WITHDRAW[plant.species_id] += 1
        return orig_action(trig, plant, world, env, owner, swarm_pop, active, entities)

    def adv_probe(sub: Any, entity_id: Any, world: Any, env: Any, swarm_pop: Any, active: Any, dead: Any) -> None:
        was_active = sub.active
        orig_adv(sub, entity_id, world, env, swarm_pop, active, dead)
        if not was_active and sub.active:
            _SUB_ACT[sub.substance_id] += 1

    triggers._process_single_trigger_action = action_probe  # type: ignore[assignment]
    synthesis._process_advance_single_synthesis = adv_probe  # type: ignore[assignment]
    _PROBE_STATE["installed"] = True


# ---------------------------------------------------------------------------
# Simulation driver
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class Sample:
    """One sampled community snapshot."""

    tick: int
    occ_pct: float
    plants: list[int]
    heads: list[int]
    swarms: list[int]
    cum_subs: list[int]
    cum_withdraw: list[int]


def _take_sample(loop: Any, area: float, swarm_comp_cls: Any) -> Sample | None:
    """Snapshot per-guild plant, herbivore, and signaling tallies from live telemetry."""
    row = loop.telemetry.get_latest_metrics()
    if row is None:
        return None
    raw_plants = row.get("plant_pop_by_species", {}) or {}
    plant_map = {int(k): int(v) for k, v in dict(raw_plants).items()}
    plants = [plant_map.get(i, 0) for i in range(N_FLORA)]
    heads = [0] * N_HERB
    swarms = [0] * N_HERB
    for entity in loop.world.query(swarm_comp_cls):
        sw = entity.get_component(swarm_comp_cls)
        if 0 <= sw.species_id < N_HERB:
            heads[sw.species_id] += sw.population
            swarms[sw.species_id] += 1
    return Sample(
        tick=loop.tick,
        occ_pct=100.0 * sum(plants) / area,
        plants=plants,
        heads=heads,
        swarms=swarms,
        cum_subs=[_SUB_ACT.get(i, 0) for i in range(N_SUB)],
        cum_withdraw=[_WITHDRAW.get(i, 0) for i in (0, 1, 2)],
    )


async def _drive_simulation(
    loop: Any,
    area: float,
    swarm_comp_cls: Any,
    max_ticks: int,
    sample_every: int,
    observer: Any,
) -> list[Sample]:
    """Step the simulation loop up to ``max_ticks`` while collecting periodic samples."""
    samples: list[Sample] = []
    for _ in range(max_ticks):
        result = await loop.step()
        if loop.tick % sample_every != 0 and not result.terminated:
            continue
        sample = _take_sample(loop, area, swarm_comp_cls)
        if sample is not None:
            samples.append(sample)
            if observer is not None:
                observer(sample, samples)
        if result.terminated:
            break
    return samples


def simulate(
    cfg_dict: dict[str, Any],
    seed: int,
    observer: Any = None,
    max_ticks: int = MAX_TICKS,
    sample_every: int = SAMPLE_EVERY,
) -> list[Sample]:
    """Run one headless simulation and return periodic community samples.

    ``observer(sample, samples)`` is invoked after each sample and may raise to abort the run.
    """
    _install_probe()
    _SUB_ACT.clear()
    _WITHDRAW.clear()
    random.seed(seed)
    np.random.seed(seed)

    from phids.api.schemas.simulation import SimulationConfig
    from phids.engine.components.swarm import SwarmComponent
    from phids.engine.loop import SimulationLoop

    cfg = SimulationConfig.model_validate(cfg_dict)
    cfg.max_ticks = max_ticks + 1
    loop = SimulationLoop(cfg, disable_replay=True)
    area = float(cfg.grid_width * cfg.grid_height)
    return asyncio.run(_drive_simulation(loop, area, SwarmComponent, max_ticks, sample_every, observer))


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def _mean(xs: list[float]) -> float:
    """Arithmetic mean with an empty-list guard."""
    return sum(xs) / len(xs) if xs else 0.0


def _cv(xs: list[float]) -> float:
    """Population coefficient of variation (``9.99`` for a non-positive mean)."""
    m = _mean(xs)
    return 9.99 if m <= 0 else statistics.pstdev(xs) / m


def equitability(counts: list[int]) -> float:
    """Shannon equitability ``J = H / ln(S)`` over a fixed species count."""
    pos = [c for c in counts if c > 0]
    total = sum(pos)
    if len(counts) < 2 or total <= 0:
        return 0.0
    h = -sum((c / total) * math.log(c / total) for c in pos)
    return h / math.log(len(counts))


def band_score(x: float, plateau: tuple[float, float], soft: tuple[float, float], zero: tuple[float, float]) -> float:
    """Piecewise-linear band score: 1 on the plateau, 0.5 at the soft edge, 0 at the zero edge."""
    if plateau[0] <= x <= plateau[1]:
        return 1.0
    if x < plateau[0]:
        if x >= soft[0]:
            return 0.5 + 0.5 * (x - soft[0]) / (plateau[0] - soft[0])
        return 0.0 if x <= zero[0] else 0.5 * (x - zero[0]) / (soft[0] - zero[0])
    if x <= soft[1]:
        return 0.5 + 0.5 * (soft[1] - x) / (soft[1] - plateau[1])
    return 0.0 if x >= zero[1] else 0.5 * (zero[1] - x) / (zero[1] - soft[1])


def _rng_stats(xs: list[float]) -> dict[str, float]:
    """Min / median / max triple."""
    return {"min": round(min(xs), 3), "median": round(statistics.median(xs), 3), "max": round(max(xs), 3)}


def summarize(samples: list[Sample], t0: int, t1: int) -> dict[str, Any] | None:
    """Score the community trajectory inside ``[t0, t1]`` and return components plus diagnostics."""
    win = [s for s in samples if t0 <= s.tick <= t1]
    if len(win) < 3:
        return None
    occ = [s.occ_pct for s in win]
    jf = [equitability(s.plants) for s in win]
    jh = [equitability(s.heads) for s in win]
    series = [[float(s.heads[g]) for s in win] for g in range(N_HERB)]
    cvs = [_cv(x) for x in series]
    meds = [statistics.median(x) for x in series]
    anchor_tick = max(win[0].tick, t1 - CASCADE_SPAN)
    anchor = next((s for s in samples if s.tick >= anchor_tick), win[0])
    last = win[-1]
    d_subs = [last.cum_subs[i] - anchor.cum_subs[i] for i in range(N_SUB)]
    d_wd = [last.cum_withdraw[i] - anchor.cum_withdraw[i] for i in range(3)]
    comps = {
        "occupancy": band_score(_mean(occ), (35.0, 60.0), (30.0, 65.0), (20.0, 75.0)),
        "flora_j": min(1.0, _mean(jf) / 0.85),
        "herb_j": min(1.0, _mean(jh) / 0.75),
        "cv": _mean([band_score(c, (0.12, 0.50), (0.05, 0.80), (0.0, 1.5)) for c in cvs]),
        "cascade": sum(1 for d in d_subs + d_wd if d > 0) / N_CASCADE_CHANNELS,
        "headcount": _mean([band_score(m, (100.0, 600.0), (40.0, 900.0), (5.0, 1800.0)) for m in meds]),
    }
    score = sum(WEIGHTS[k] * v for k, v in comps.items())
    return {
        "score": round(score, 5),
        "components": {k: round(v, 4) for k, v in comps.items()},
        "window": [win[0].tick, last.tick],
        "occupancy": _rng_stats(occ),
        "j_flora": {"mean": round(_mean(jf), 4), "final": round(jf[-1], 4)},
        "j_herb": {"mean": round(_mean(jh), 4), "final": round(jh[-1], 4)},
        "herb_guild_heads": [_rng_stats(x) for x in series],
        "herb_guild_cv": [round(c, 3) for c in cvs],
        "flora_species_counts": [_rng_stats([float(s.plants[i]) for s in win]) for i in range(N_FLORA)],
        "final_plants": last.plants,
        "final_heads": last.heads,
        "final_swarms": last.swarms,
        "final_occupancy_pct": round(last.occ_pct, 2),
        "delta_subs": d_subs,
        "delta_withdraw": d_wd,
    }


def hard_rule(s: Sample) -> str | None:
    """Return the name of the violated hard rule for a sample, or ``None``."""
    if min(s.plants) == 0:
        return "flora_extinct"
    if s.tick >= 400 and s.occ_pct < 15.0:
        return "occupancy_floor"
    if s.tick >= 1200:
        if min(s.heads) == 0:
            return "herbivore_extinct"
        if s.occ_pct > 72.0:
            return "occupancy_ceiling"
        total = sum(s.heads)
        if total > 0 and max(s.heads) / total > 0.65:
            return "herbivore_dominance"
    return None


def proxy_window(tick: int) -> tuple[int, int]:
    """Scoring window used for intermediate (pruner) values at a given checkpoint."""
    return (1000, tick) if tick >= MAX_TICKS else (max(200, tick - 1000), tick)


# ---------------------------------------------------------------------------
# Optuna objective and workers
# ---------------------------------------------------------------------------


def _evaluate_sample_pruning(trial: optuna.Trial, sample: Sample, samples: list[Sample]) -> None:
    """Enforce hard ecological rules and ASHA intermediate pruning checks on a sample."""
    reason = hard_rule(sample)
    if reason is not None:
        partial = summarize(samples, max(0, sample.tick - 1000), sample.tick)
        trial.report((partial["score"] if partial else 0.0) - 1.0, sample.tick)
        trial.set_user_attr("reason", f"{reason}@{sample.tick}")
        raise optuna.TrialPruned(reason)
    if sample.tick not in CHECKPOINTS:
        return
    t0, t1 = proxy_window(sample.tick)
    partial = summarize(samples, t0, t1)
    trial.report(partial["score"] if partial else 0.0, sample.tick)
    if sample.tick < MAX_TICKS and trial.should_prune():
        trial.set_user_attr("reason", f"asha@{sample.tick}")
        raise optuna.TrialPruned("asha")


def objective(trial: optuna.Trial, base_cfg: dict[str, Any]) -> float:
    """Evaluate one parameter set with ASHA checkpoints and hard-rule pruning."""
    params = {name: trial.suggest_float(name, lo, hi) for name, (lo, hi) in SEARCH_SPACE.items()}
    cfg = apply_params(base_cfg, params)
    t_start = time.perf_counter()

    try:
        samples = simulate(
            cfg,
            TUNE_SEED,
            observer=lambda sample, hist: _evaluate_sample_pruning(trial, sample, hist),
        )
    except optuna.TrialPruned:
        trial.set_user_attr("elapsed_s", round(time.perf_counter() - t_start, 1))
        raise
    except Exception:
        traceback.print_exc()
        raise
    trial.set_user_attr("elapsed_s", round(time.perf_counter() - t_start, 1))
    if not samples or samples[-1].tick < MAX_TICKS:
        trial.set_user_attr("reason", "terminated_early")
        raise optuna.TrialPruned("terminated_early")
    final = summarize(samples, *proxy_window(MAX_TICKS))
    if final is None:
        raise optuna.TrialPruned("no_window")
    trial.set_user_attr("metrics", final)
    return float(final["score"])


def _journal_path(study_name: str) -> Path:
    """Journal file for a named study."""
    return OUT_DIR / f"{study_name}.journal"


def _storage(study_name: str) -> JournalStorage:
    """Open the multi-process-safe journal storage for a study."""
    return JournalStorage(JournalFileBackend(str(_journal_path(study_name))))


def _make_pruner() -> optuna.pruners.SuccessiveHalvingPruner:
    """ASHA pruner with the specified resource schedule."""
    return optuna.pruners.SuccessiveHalvingPruner(min_resource=400, reduction_factor=3, min_early_stopping_rate=0)


def _progress(_study: optuna.Study, trial: optuna.trial.FrozenTrial) -> None:
    """Print one concise line per finished trial."""
    val = f"{trial.value:.4f}" if trial.value is not None else "  n/a "
    print(
        f"TRIAL {trial.number:3d} {trial.state.name:8s} value={val} "
        f"reason={trial.user_attrs.get('reason', '-')} t={trial.user_attrs.get('elapsed_s', '?')}s",
        flush=True,
    )


def _worker(args: tuple[int, str, int]) -> int:
    """Run one Optuna worker against the shared journal until the trial budget is exhausted."""
    idx, study_name, total = args
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    sampler = optuna.samplers.TPESampler(seed=42 + idx, multivariate=True, constant_liar=True, n_startup_trials=16)
    study = optuna.load_study(
        study_name=study_name, storage=_storage(study_name), sampler=sampler, pruner=_make_pruner()
    )
    base = base_config_dict(128, 64)
    study.optimize(
        lambda t: objective(t, base),
        callbacks=[
            MaxTrialsCallback(total, states=(TrialState.COMPLETE, TrialState.PRUNED, TrialState.FAIL)),
            _progress,
        ],
        catch=(Exception,),
    )
    return idx


def cmd_tune(args: argparse.Namespace) -> None:
    """Create (or resume) the study and run parallel workers."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    study = optuna.create_study(
        study_name=args.study,
        storage=_storage(args.study),
        sampler=optuna.samplers.TPESampler(seed=42, multivariate=True, constant_liar=True, n_startup_trials=16),
        pruner=_make_pruner(),
        direction="maximize",
        load_if_exists=True,
    )
    if not study.trials:
        study.enqueue_trial(BASELINE, skip_if_exists=True)
    t0 = time.perf_counter()
    jobs = [(i, args.study, args.trials) for i in range(args.workers)]
    with ProcessPoolExecutor(max_workers=args.workers, mp_context=mp.get_context("spawn")) as ex:
        list(ex.map(_worker, jobs))
    print(f"TUNE_DONE elapsed={time.perf_counter() - t0:.1f}s")
    cmd_status(args)


def _load(study_name: str) -> optuna.Study:
    """Load an existing study (read access)."""
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    return optuna.load_study(study_name=study_name, storage=_storage(study_name))


def cmd_status(args: argparse.Namespace) -> None:
    """Print state counts and the leaderboard."""
    study = _load(args.study)
    states = Counter(t.state.name for t in study.trials)
    reasons = Counter(t.user_attrs.get("reason", "-").split("@")[0] for t in study.trials if t.state.name == "PRUNED")
    print("STATES", dict(states), "PRUNE_REASONS", dict(reasons))
    done = sorted((t for t in study.trials if t.state == TrialState.COMPLETE), key=lambda t: -(t.value or 0.0))
    for t in done[:10]:
        comps = t.user_attrs.get("metrics", {}).get("components", {})
        rounded = {k: round(v, 3) for k, v in t.params.items()}
        print(f"  #{t.number:3d} score={t.value:.4f} comps={comps} params={rounded}")


def _top_params(study_name: str, top: int) -> list[tuple[int, float, dict[str, float]]]:
    """Return ``(trial_number, value, params)`` of the best trials, padding from ASHA rungs if needed."""
    study = _load(study_name)
    done = sorted((t for t in study.trials if t.state == TrialState.COMPLETE), key=lambda t: -(t.value or 0.0))
    selected = [(t.number, float(t.value or 0.0), dict(t.params)) for t in done[:top]]
    if len(selected) < top:
        asha_cands: list[tuple[int, float, optuna.trial.FrozenTrial]] = []
        for t in study.trials:
            reason = str(t.user_attrs.get("reason", ""))
            if t.state == TrialState.PRUNED and reason.startswith("asha@"):
                step = int(reason.split("@")[1])
                asha_cands.append((step, float(t.intermediate_values.get(step, -9.0)), t))
        asha_cands.sort(key=lambda item: (item[0], item[1]), reverse=True)
        for _, val, t in asha_cands[: top - len(selected)]:
            selected.append((t.number, val, dict(t.params)))
    return selected


def _eval_job(job: tuple[int, dict[str, float], int, int, int, int]) -> dict[str, Any]:
    """Evaluate one ``(trial, params, seed, width, height, sample_every)`` job on the full horizon."""
    trial_no, params, seed, width, height, sample_every = job
    t0 = time.perf_counter()
    samples = simulate(tuned_config_dict(width, height, params), seed, sample_every=sample_every)
    summary = summarize(samples, 1000, MAX_TICKS)
    violations = sorted({r for s in samples if (r := hard_rule(s)) is not None})
    return {
        "trial": trial_no,
        "seed": seed,
        "grid": [width, height],
        "elapsed_s": round(time.perf_counter() - t0, 1),
        "last_tick": samples[-1].tick if samples else 0,
        "violations": violations,
        "summary": summary,
        "trajectory": [
            {
                "tick": s.tick,
                "occ": round(s.occ_pct, 2),
                "plants": s.plants,
                "heads": s.heads,
                "swarms": s.swarms,
            }
            for s in samples
            if s.tick % 500 == 0
        ],
    }


def cmd_validate(args: argparse.Namespace) -> None:
    """Re-evaluate the top candidates on the held-out validation seeds."""
    top = _top_params(args.study, args.top)
    jobs = [(n, p, seed, 128, 64, SAMPLE_EVERY) for n, _, p in top for seed in VALIDATION_SEEDS]
    with ProcessPoolExecutor(max_workers=args.workers, mp_context=mp.get_context("spawn")) as ex:
        results = list(ex.map(_eval_job, jobs))
    out = OUT_DIR / f"validation_{args.study}.json"
    out.write_text(
        json.dumps(
            {"candidates": [{"trial": n, "value": v, "params": p} for n, v, p in top], "runs": results}, indent=1
        ),
        encoding="utf-8",
    )
    for r in results:
        sm = r["summary"] or {}
        print(
            f"VAL trial={r['trial']:3d} seed={r['seed']} t={r['elapsed_s']}s last={r['last_tick']} "
            f"score={sm.get('score')} viol={r['violations']} occ={sm.get('final_occupancy_pct')} "
            f"heads={sm.get('final_heads')} plants={sm.get('final_plants')}",
            flush=True,
        )
    print(f"VALIDATION_SAVED {out}")


def cmd_export(args: argparse.Namespace) -> None:
    """Write tuned scenario JSONs for a trial (128 x 64 twin and 256 x 256 flagship)."""
    study = _load(args.study)
    params = dict(study.trials[args.trial].params)
    SCENARIO_DIR.mkdir(parents=True, exist_ok=True)
    for w, h, name in (
        (128, 64, "riparian_meadow_ecotone_128x64_twin.json"),
        (256, 256, "riparian_meadow_ecotone_256x256.json"),
    ):
        from phids.api.schemas.simulation import SimulationConfig

        cfg = SimulationConfig.model_validate(tuned_config_dict(w, h, params))
        path = SCENARIO_DIR / name
        path.write_text(json.dumps(cfg.model_dump(mode="json"), indent=2), encoding="utf-8")
        print(f"EXPORTED {path}")
    print("PARAMS", json.dumps({k: round(v, 4) for k, v in params.items()}))


def cmd_confirm(args: argparse.Namespace) -> None:
    """Run one full-horizon confirmation of a trial on an arbitrary grid and seed."""
    params = dict(_load(args.study).trials[args.trial].params)
    res = _eval_job((args.trial, params, args.seed, args.width, args.height, args.sample_every))
    out = OUT_DIR / f"confirm_{args.width}x{args.height}_trial{args.trial}_seed{args.seed}.json"
    out.write_text(json.dumps(res, indent=1), encoding="utf-8")
    print("CONFIRM", json.dumps(res))


def cmd_smoke(args: argparse.Namespace) -> None:
    """Evaluate the unmodified baseline on the tuning seed (pipeline sanity check)."""
    t0 = time.perf_counter()
    samples = simulate(tuned_config_dict(128, 64, BASELINE), TUNE_SEED, max_ticks=args.max_ticks)
    viol = [(s.tick, r) for s in samples if (r := hard_rule(s)) is not None][:3]
    summary = summarize(samples, 1000 if args.max_ticks >= 2000 else 200, args.max_ticks)
    print(
        "SMOKE",
        json.dumps({"elapsed_s": round(time.perf_counter() - t0, 1), "first_violations": viol, "summary": summary}),
    )


def main() -> None:
    """Parse the command line and dispatch the sub-command."""
    os.environ["NUMBA_NUM_THREADS"] = "1"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", default=DEFAULT_STUDY)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("smoke")
    p.add_argument("--max-ticks", type=int, default=MAX_TICKS)
    p.set_defaults(fn=cmd_smoke)
    p = sub.add_parser("tune")
    p.add_argument("--trials", type=int, default=72)
    p.add_argument("--workers", type=int, default=4)
    p.set_defaults(fn=cmd_tune)
    p = sub.add_parser("status")
    p.set_defaults(fn=cmd_status)
    p = sub.add_parser("validate")
    p.add_argument("--top", type=int, default=5)
    p.add_argument("--workers", type=int, default=4)
    p.set_defaults(fn=cmd_validate)
    p = sub.add_parser("export")
    p.add_argument("--trial", type=int, required=True)
    p.set_defaults(fn=cmd_export)
    p = sub.add_parser("confirm")
    p.add_argument("--trial", type=int, required=True)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--width", type=int, default=256)
    p.add_argument("--height", type=int, default=256)
    p.add_argument("--sample-every", type=int, default=100)
    p.set_defaults(fn=cmd_confirm)
    args = parser.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
