# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Simulation performance comparison benchmark.

Measures wall-clock ticks per second under different JIT modes and commits without modifying the active workspace
branch. Compares ticks per second across different JIT modes and commits/branches. Also checks if the
simulation runs correctly by comparing the simulation results with the reference results.

Usage:
    python scripts/run_sim_benchmark.py <scenario_path> [ticks]
    python scripts/run_sim_benchmark.py <scenario_path> [ticks] --compare <ref1> <ref2>

Example:
    python scripts/run_sim_benchmark.py scenarios/basic.json 100
    python scripts/run_sim_benchmark.py scenarios/basic.json 100 --compare main feat/new-interaction-model
"""

import argparse
import asyncio
import os
import shutil
import statistics
import subprocess
import sys
import time

from phids.engine.loop import SimulationLoop
from phids.io.scenario import load_scenario_from_json


async def run_benchmark(scenario_path: str, num_ticks: int = 1000, warmup_ticks: int = 10) -> tuple[float, int]:
    """Run the simulation benchmark.

    Args:
        scenario_path: Path to scenario JSON file
        num_ticks: Number of ticks to simulate
        warmup_ticks: Number of warmup ticks

    Returns:
        A tuple of (duration, actual_ticks)
    """
    config = load_scenario_from_json(scenario_path)
    # run headless without recording replays for raw engine performance
    loop = SimulationLoop(config, disable_replay=True)
    loop.running = True

    # Warmup to trigger JIT compilation if enabled
    for _ in range(warmup_ticks):
        result = await loop.step()
        if result.terminated:
            loop = SimulationLoop(config, disable_replay=True)
            loop.running = True

    t0 = time.perf_counter()
    actual_ticks = 0
    for _ in range(num_ticks):
        result = await loop.step()
        actual_ticks += 1
        if result.terminated:
            break
    t1 = time.perf_counter()
    duration = t1 - t0
    return duration, actual_ticks


def run_in_subprocess(
    cwd: str, scenario_path: str, num_ticks: int, disable_jit: bool, repeats: int, warmup: int
) -> tuple[float | None, int]:
    """Run the simulation benchmark in a subprocess.

    Args:
        cwd: Working directory
        scenario_path: Path to scenario JSON file
        num_ticks: Number of ticks to simulate
        disable_jit: Disable JIT compilation
        repeats: Number of repeats
        warmup: Number of warmup ticks

    Returns:
        A tuple of (duration, actual_ticks)
    """
    env = os.environ.copy()
    env["NUMBA_DISABLE_JIT"] = "1" if disable_jit else "0"

    # Call the copy of ourselves under .cache using the active sys.executable
    script_path = "scripts/run_sim_benchmark.py"
    cmd = [
        sys.executable,
        script_path,
        "--internal-run",
        scenario_path,
        str(num_ticks),
        "--warmup",
        str(warmup),
    ]

    durations = []
    total_ticks = 0
    for i in range(1, repeats + 1):
        print(f"    -> Run {i}/{repeats} ... ", end="", flush=True)
        res = subprocess.run(cmd, env=env, cwd=cwd, capture_output=True, text=True)

        if res.returncode != 0:
            print("FAIL")
            print(f"Error running benchmark subprocess (JIT={not disable_jit}): {res.stderr.strip()}")
            return None, 0
        try:
            parts = res.stdout.strip().split(",")
            duration = float(parts[0])
            ticks = int(parts[1])
            durations.append(duration)
            total_ticks += ticks
            print(f"OK ({duration:.2f}s)")
        except ValueError:
            print("PARSE ERROR")
            print(f"Failed to parse subprocess output: {res.stdout}")
            return None, 0

    avg_dur = statistics.mean(durations) if durations else 0
    return avg_dur, total_ticks


def git_cmd(args: list[str], cwd: str | None = None) -> str:
    """Run a git command and return the output.

    Args:
        args: Arguments to pass to git
        cwd: Working directory

    Returns:
        Output of the git command
    """
    res = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"Git command {' '.join(args)} failed: {res.stderr.strip()}")
    return res.stdout.strip()


def run_compare(ref1: str, ref2: str, scenario_path: str, num_ticks: int, repeats: int, warmup: int) -> None:
    """Run a performance comparison between two git references.

    Args:
        ref1: First git reference
        ref2: Second git reference
        scenario_path: Path to scenario JSON file
        num_ticks: Number of ticks to simulate
        repeats: Number of repeats
        warmup: Number of warmup ticks
    """
    print(f"Comparing performance between '{ref1}' and '{ref2}' on {scenario_path} ({num_ticks} ticks)...")
    print(f"Repeats per test: {repeats} | Warmup ticks: {warmup}")

    # Create .cache if it doesn't exist
    os.makedirs(".cache", exist_ok=True)

    clone_path = os.path.join(".cache", "bench_clone")
    if os.path.exists(clone_path):
        shutil.rmtree(clone_path, ignore_errors=True)

    print("Creating virtual repository clone in .cache/bench_clone...")
    # --shared uses hardlinks to the local object store (near-instant and zero-copy)
    git_cmd(["clone", "--shared", ".", clone_path])

    # Ensure scripts directory exists in clone
    os.makedirs(os.path.join(clone_path, "scripts"), exist_ok=True)
    # Copy ourselves into the clone so we are guaranteed to run this version of the script
    shutil.copy2(__file__, os.path.join(clone_path, "scripts", "run_sim_benchmark.py"))

    results = {}
    try:
        for ref in [ref1, ref2]:
            print(f"\n[Virtual Clone] Checking out '{ref}'...")
            git_cmd(["checkout", ref], cwd=clone_path)

            # Since checking out old commits might delete the script copy, re-copy it to be safe
            shutil.copy2(__file__, os.path.join(clone_path, "scripts", "run_sim_benchmark.py"))

            print(f"[Virtual Clone] Running benchmark on '{ref}' (JIT enabled)...")
            jit_dur, jit_ticks = run_in_subprocess(
                clone_path, scenario_path, num_ticks, disable_jit=False, repeats=repeats, warmup=warmup
            )

            print(f"[Virtual Clone] Running benchmark on '{ref}' (JIT disabled)...")
            nojit_dur, nojit_ticks = run_in_subprocess(
                clone_path, scenario_path, num_ticks, disable_jit=True, repeats=repeats, warmup=warmup
            )

            results[ref] = {
                "jit_dur": jit_dur,
                "jit_ticks": jit_ticks,
                "nojit_dur": nojit_dur,
                "nojit_ticks": nojit_ticks,
            }
    finally:
        print("\nCleaning up virtual repository clone...")
        shutil.rmtree(clone_path, ignore_errors=True)

    # Print results
    print("\n" + "=" * 80)
    headers = (
        f"{'Commit / Ref':<30} | {'JIT Mode':<10} | "
        f"{'Avg Duration (s)':<16} | {'Total Ticks':<11} | {'Avg Ticks/s':<11}"
    )
    print(headers)
    print("=" * 80)
    for ref, res in results.items():
        for mode in ["JIT", "No-JIT"]:
            dur_val = res["jit_dur"] if mode == "JIT" else res["nojit_dur"]
            ticks_val = res["jit_ticks"] if mode == "JIT" else res["nojit_ticks"]
            if dur_val is not None and ticks_val is not None and dur_val > 0:
                dur: float = float(dur_val)
                ticks: int = int(ticks_val)
                tps = f"{(ticks / repeats) / dur:.2f}"
                dur_str = f"{dur:.4f}"
            else:
                tps = "N/A"
                dur_str = "N/A"
            print(f"{ref:<30} | {mode:<10} | {dur_str:<16} | {ticks_val:<11} | {tps:<11}")
    print("=" * 80)

    # Determine more recent vs less recent commit/ref using git logs
    try:
        time_ref1 = int(git_cmd(["log", "-1", "--format=%ct", ref1]))
        time_ref2 = int(git_cmd(["log", "-1", "--format=%ct", ref2]))
        if time_ref1 >= time_ref2:
            opt_ref, base_ref = ref1, ref2
        else:
            opt_ref, base_ref = ref2, ref1
    except Exception:
        # Fallback if refs aren't standard git commits (e.g. branch names)
        opt_ref, base_ref = ref1, ref2

    print("\n" + "=" * 80)
    print("Evaluation Summary")
    print("=" * 80)
    print(f"- Baseline Version:  {base_ref}")
    print(f"- Optimized Version: {opt_ref}")
    print("-" * 80)

    for mode in ["JIT", "No-JIT"]:
        key_dur = "jit_dur" if mode == "JIT" else "nojit_dur"
        key_ticks = "jit_ticks" if mode == "JIT" else "nojit_ticks"

        base_dur_val = results[base_ref][key_dur]
        base_ticks_val = results[base_ref][key_ticks]
        opt_dur_val = results[opt_ref][key_dur]
        opt_ticks_val = results[opt_ref][key_ticks]

        if (
            base_dur_val is not None
            and opt_dur_val is not None
            and base_ticks_val is not None
            and opt_ticks_val is not None
            and base_dur_val > 0
            and opt_dur_val > 0
        ):
            bd: float = float(base_dur_val)
            od: float = float(opt_dur_val)
            base_t: int = int(base_ticks_val)
            opt_t: int = int(opt_ticks_val)

            base_tps = (base_t / repeats) / bd
            opt_tps = (opt_t / repeats) / od

            diff_pct = ((opt_tps - base_tps) / base_tps) * 100
            faster_slower = "faster" if diff_pct >= 0 else "slower"

            print(f"{mode} Mode:")
            print(f"  * Baseline:  {base_tps:.2f} ticks/s ({bd:.4f}s)")
            print(f"  * Optimized: {opt_tps:.2f} ticks/s ({od:.4f}s)")
            print(f"  * Result:    Optimized is {abs(diff_pct):.2f}% {faster_slower}.")
        else:
            print(f"{mode} Mode: N/A (runs failed)")
        print("-" * 80)


if __name__ == "__main__":
    """Command-line interface for running PHIDS benchmarks.

    This script provides:
    1. A single run benchmark on the current directory
    2. A branch comparison between two git refs/commits
    3. A virtual repository clone using git --shared for efficient comparison
    """
    parser = argparse.ArgumentParser(description="PHIDS Simulation Benchmark and Branch Comparer")

    parser.add_argument("scenario", help="Path to scenario JSON file")
    parser.add_argument("ticks", type=int, nargs="?", default=100, help="Number of ticks to simulate")
    parser.add_argument("--compare", nargs=2, metavar=("REF1", "REF2"), help="Compare two git refs/commits")
    parser.add_argument("--repeats", "-r", type=int, default=1, help="Number of times to repeat the run for averaging")
    parser.add_argument(
        "--warmup", "-w", type=int, default=10, help="Number of warmup ticks to compile JIT before timing"
    )
    parser.add_argument("--internal-run", action="store_true", help=argparse.SUPPRESS)

    args = parser.parse_args()

    if args.internal_run:
        # Silence standard logging to only output clean results
        import logging

        logging.getLogger().setLevel(logging.ERROR)
        dur, actual_ticks = asyncio.run(run_benchmark(args.scenario, args.ticks, args.warmup))
        print(f"{dur},{actual_ticks}")
    elif args.compare:
        ref1, ref2 = args.compare
        run_compare(ref1, ref2, args.scenario, args.ticks, args.repeats, args.warmup)
    else:
        # Single run benchmark on current directory
        dur, actual_ticks = asyncio.run(run_benchmark(args.scenario, args.ticks, args.warmup))
        print(f"Ticks simulated: {actual_ticks}")
        print(f"Duration: {dur:.4f} seconds ({actual_ticks / dur:.2f} ticks/s)")
