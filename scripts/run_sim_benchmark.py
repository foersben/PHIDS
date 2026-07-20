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


def _setup_virtual_clone(clone_path: str) -> None:
    """Create a fast hardlinked clone of the repository.

    This enables side-by-side performance comparison against different git refs
    without altering the working tree or dirtying the local workspace. By using
    --shared, it creates near-instant hardlinks to the local object store.

    Args:
        clone_path: Path where the virtual clone should be created.
    """
    if os.path.exists(clone_path):
        shutil.rmtree(clone_path, ignore_errors=True)

    print("Creating virtual repository clone in .cache/bench_clone...")
    # --shared uses hardlinks to the local object store (near-instant and zero-copy)
    git_cmd(["clone", "--shared", ".", clone_path])

    # Ensure scripts directory exists in clone
    os.makedirs(os.path.join(clone_path, "scripts"), exist_ok=True)
    # Copy ourselves into the clone so we are guaranteed to run this version of the script
    shutil.copy2(__file__, os.path.join(clone_path, "scripts", "run_sim_benchmark.py"))


def _execute_suite(
    ref1: str,
    ref2: str,
    scenarios: list[str],
    num_ticks: int,
    repeats: int,
    warmup: int,
    jit_only: bool,
    clone_path: str,
) -> dict[str, dict[str, dict[str, float | int | None]]]:
    """Execute the benchmark suite for both references across all scenarios.

    For each git reference and each scenario, this routine orchestrates the
    subprocess benchmark execution (with and without JIT if configured). If
    the 'worktree' keyword is specified, the current active workspace is used
    instead of the virtual clone to capture uncommitted changes.

    Args:
        ref1: The first git reference (or 'worktree').
        ref2: The second git reference (or 'worktree').
        scenarios: List of scenario file paths.
        num_ticks: Total ticks to simulate per run.
        repeats: Iterations per benchmark run for averaging.
        warmup: Number of warmup ticks.
        jit_only: If true, skips No-JIT performance measurements.
        clone_path: Path to the virtual clone directory.

    Returns:
        A nested dictionary mapping scenario paths to ref results.
    """
    results: dict[str, dict[str, dict[str, float | int | None]]] = {}
    try:
        for ref in [ref1, ref2]:
            if ref.lower() == "worktree":
                print(f"\n[Working Tree] Using current uncommitted state for '{ref}'...")
                target_cwd = "."
                env_label = "Working Tree"
            else:
                print(f"\n[Virtual Clone] Checking out '{ref}'...")
                git_cmd(["checkout", "-f", ref], cwd=clone_path)
                # Since checking out old commits might delete the script copy, re-copy it to be safe
                shutil.copy2(__file__, os.path.join(clone_path, "scripts", "run_sim_benchmark.py"))
                target_cwd = clone_path
                env_label = "Virtual Clone"

            for scenario_path in scenarios:
                if scenario_path not in results:
                    results[scenario_path] = {}

                print(
                    f"[{env_label}] Running benchmark on '{ref}' (JIT enabled) for {os.path.basename(scenario_path)}..."
                )
                jit_dur, jit_ticks = run_in_subprocess(
                    target_cwd, scenario_path, num_ticks, disable_jit=False, repeats=repeats, warmup=warmup
                )

                if not jit_only:
                    print(
                        f"[{env_label}] Running benchmark on '{ref}' (JIT disabled) "
                        f"for {os.path.basename(scenario_path)}..."
                    )
                    nojit_dur, nojit_ticks = run_in_subprocess(
                        target_cwd, scenario_path, num_ticks, disable_jit=True, repeats=repeats, warmup=warmup
                    )
                else:
                    nojit_dur, nojit_ticks = None, 0

                results[scenario_path][ref] = {
                    "jit_dur": jit_dur,
                    "jit_ticks": jit_ticks,
                    "nojit_dur": nojit_dur,
                    "nojit_ticks": nojit_ticks,
                }
    finally:
        print("\nCleaning up virtual repository clone...")
        shutil.rmtree(clone_path, ignore_errors=True)
    return results


def _print_scenario_table(
    scenario_name: str,
    scenario_res: dict[str, dict[str, float | int | None]],
    modes: list[str],
    repeats: int,
) -> None:
    """Print the detailed benchmark raw table for a single scenario."""
    print("\n" + "=" * 100)
    print(f"Results for Scenario: {scenario_name}")
    print("=" * 100)
    headers = (
        f"{'Commit / Ref':<40} | {'JIT Mode':<10} | "
        f"{'Avg Duration (s)':<16} | {'Total Ticks':<11} | {'Avg Ticks/s':<11}"
    )
    print(headers)
    print("-" * 100)

    for ref, res in scenario_res.items():
        for mode in modes:
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
            print(f"{ref:<40} | {mode:<10} | {dur_str:<16} | {ticks_val:<11} | {tps:<11}")


def _print_scenario_summary(
    scenario_name: str,
    scenario_res: dict[str, dict[str, float | int | None]],
    base_ref: str,
    opt_ref: str,
    modes: list[str],
    repeats: int,
) -> None:
    """Print the comparative benchmark statistics for a single scenario."""
    print("\n" + "-" * 100)
    print(f"Evaluation Summary: {scenario_name}")
    print("-" * 100)
    print(f"- Baseline Version:  {base_ref}")
    print(f"- Optimized Version: {opt_ref}")

    mismatch_modes = []
    for mode in modes:
        k_ticks = "jit_ticks" if mode == "JIT" else "nojit_ticks"
        b_ticks = scenario_res[base_ref].get(k_ticks)
        o_ticks = scenario_res[opt_ref].get(k_ticks)
        if b_ticks is not None and o_ticks is not None and b_ticks != o_ticks:
            mismatch_modes.append(mode)

    if mismatch_modes:
        print(f"- [WARNING]: TICK COUNT MISMATCH DETECTED ({', '.join(mismatch_modes)})")
        print("             The simulations terminated at different points.")
        print("             Comparing 'Avg Ticks/s' is highly biased as the")
        print("             computational load per tick often changes over time.")

    print("-" * 100)

    for mode in modes:
        key_dur = "jit_dur" if mode == "JIT" else "nojit_dur"
        key_ticks = "jit_ticks" if mode == "JIT" else "nojit_ticks"

        base_dur_val = scenario_res[base_ref][key_dur]
        base_ticks_val = scenario_res[base_ref][key_ticks]
        opt_dur_val = scenario_res[opt_ref][key_dur]
        opt_ticks_val = scenario_res[opt_ref][key_ticks]

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
        print("-" * 100)


def _print_global_summary(
    results: dict[str, dict[str, dict[str, float | int | None]]],
    scenarios: list[str],
    base_ref: str,
    opt_ref: str,
    modes: list[str],
    repeats: int,
) -> None:
    """Print the aggregate overall benchmark statistics spanning all scenarios."""
    if len(scenarios) <= 1:
        return

    print("\n" + "=" * 100)
    print("Overall Folder Evaluation Summary")
    print("=" * 100)
    print(f"- Baseline Version:  {base_ref}")
    print(f"- Optimized Version: {opt_ref}")

    global_mismatches = False
    for scenario_path in scenarios:
        scen_res = results[scenario_path]
        for mode in modes:
            k_ticks = "jit_ticks" if mode == "JIT" else "nojit_ticks"
            b_ticks = scen_res[base_ref].get(k_ticks)
            o_ticks = scen_res[opt_ref].get(k_ticks)
            if b_ticks is not None and o_ticks is not None and b_ticks != o_ticks:
                global_mismatches = True
                break

    if global_mismatches:
        print("- [WARNING]: TICK MISMATCHES DETECTED IN ONE OR MORE SCENARIOS")
        print("             The overall average speed comparison is biased.")
        print("             Behavioral outcomes diverged between the branches.")

    print("-" * 100)

    for mode in modes:
        key_dur = "jit_dur" if mode == "JIT" else "nojit_dur"
        key_ticks = "jit_ticks" if mode == "JIT" else "nojit_ticks"

        total_base_dur = 0.0
        total_base_ticks = 0
        total_opt_dur = 0.0
        total_opt_ticks = 0

        all_valid = True
        for scenario_path in scenarios:
            scen_res = results[scenario_path]
            b_dur_val = scen_res[base_ref][key_dur]
            b_ticks_val = scen_res[base_ref][key_ticks]
            o_dur_val = scen_res[opt_ref][key_dur]
            o_ticks_val = scen_res[opt_ref][key_ticks]

            if (
                b_dur_val is not None
                and o_dur_val is not None
                and b_ticks_val is not None
                and o_ticks_val is not None
                and b_dur_val > 0
                and o_dur_val > 0
            ):
                total_base_dur += float(b_dur_val)
                total_base_ticks += int(b_ticks_val)
                total_opt_dur += float(o_dur_val)
                total_opt_ticks += int(o_ticks_val)
            else:
                all_valid = False

        if all_valid and total_base_dur > 0 and total_opt_dur > 0:
            base_tps = (total_base_ticks / repeats) / total_base_dur
            opt_tps = (total_opt_ticks / repeats) / total_opt_dur

            diff_pct = ((opt_tps - base_tps) / base_tps) * 100
            faster_slower = "faster" if diff_pct >= 0 else "slower"

            print(f"{mode} Mode (All Scenarios Combined):")
            print(f"  * Baseline:  {base_tps:.2f} ticks/s ({total_base_dur:.4f}s total)")
            print(f"  * Optimized: {opt_tps:.2f} ticks/s ({total_opt_dur:.4f}s total)")
            print(f"  * Result:    Optimized is {abs(diff_pct):.2f}% {faster_slower} overall.")
        else:
            print(f"{mode} Mode (All Scenarios Combined): N/A (some runs failed)")
        print("-" * 100)


def _print_tabular_results(
    results: dict[str, dict[str, dict[str, float | int | None]]],
    scenarios: list[str],
    ref1: str,
    ref2: str,
    repeats: int,
    jit_only: bool,
) -> None:
    """Print the formatted evaluation tables and summaries."""
    # Determine more recent vs less recent commit/ref using git logs
    try:
        time_ref1 = float("inf") if ref1.lower() == "worktree" else float(git_cmd(["log", "-1", "--format=%ct", ref1]))
        time_ref2 = float("inf") if ref2.lower() == "worktree" else float(git_cmd(["log", "-1", "--format=%ct", ref2]))

        if time_ref1 >= time_ref2:
            opt_ref, base_ref = ref1, ref2
        else:
            opt_ref, base_ref = ref2, ref1
    except Exception:
        # Fallback if refs aren't standard git commits (e.g. branch names)
        opt_ref, base_ref = ref1, ref2

    modes = ["JIT"] if jit_only else ["JIT", "No-JIT"]

    for scenario_path in scenarios:
        scenario_name = os.path.basename(scenario_path)
        scenario_res = results[scenario_path]
        _print_scenario_table(scenario_name, scenario_res, modes, repeats)
        _print_scenario_summary(scenario_name, scenario_res, base_ref, opt_ref, modes, repeats)

    _print_global_summary(results, scenarios, base_ref, opt_ref, modes, repeats)


def run_compare(
    ref1: str, ref2: str, scenarios: list[str], num_ticks: int, repeats: int, warmup: int, jit_only: bool
) -> None:
    """Run a performance comparison between two git references across multiple scenarios.

    Args:
        ref1: First git reference
        ref2: Second git reference
        scenarios: List of paths to scenario JSON files
        num_ticks: Number of ticks to simulate
        repeats: Number of repeats
        warmup: Number of warmup ticks
        jit_only: If True, skip the No-JIT comparisons
    """
    print(f"Comparing performance between '{ref1}' and '{ref2}' on {len(scenarios)} scenario(s) ({num_ticks} ticks)...")
    print(f"Repeats per test: {repeats} | Warmup ticks: {warmup} | JIT Only: {jit_only}")

    # Create .cache if it doesn't exist
    os.makedirs(".cache", exist_ok=True)
    clone_path = os.path.join(".cache", "bench_clone")

    _setup_virtual_clone(clone_path)
    results = _execute_suite(ref1, ref2, scenarios, num_ticks, repeats, warmup, jit_only, clone_path)
    _print_tabular_results(results, scenarios, ref1, ref2, repeats, jit_only)


if __name__ == "__main__":
    """Command-line interface for running PHIDS benchmarks.

    This script provides:
    1. A single run benchmark on the current directory
    2. A branch comparison between two git refs/commits
    3. A virtual repository clone using git --shared for efficient comparison
    4. Support for 'worktree' keyword to safely benchmark the current uncommitted state
    """
    parser = argparse.ArgumentParser(description="PHIDS Simulation Benchmark and Branch Comparer")

    parser.add_argument("scenario", help="Path to scenario JSON file or directory containing JSON files")
    parser.add_argument("ticks", type=int, nargs="?", default=100, help="Number of ticks to simulate")
    parser.add_argument(
        "--compare",
        nargs=2,
        metavar=("REF1", "REF2"),
        help="Compare two git refs/commits (use 'worktree' for current uncommitted state)",
    )
    parser.add_argument("--repeats", "-r", type=int, default=1, help="Number of times to repeat the run for averaging")
    parser.add_argument(
        "--warmup", "-w", type=int, default=10, help="Number of warmup ticks to compile JIT before timing"
    )
    parser.add_argument("--jit-only", action="store_true", help="Only test and compare the JIT versions (skip No-JIT)")
    parser.add_argument("--internal-run", action="store_true", help=argparse.SUPPRESS)

    args = parser.parse_args()

    path = args.scenario
    if os.path.isdir(path):
        scenarios = [os.path.join(path, f) for f in os.listdir(path) if f.endswith(".json")]
        scenarios.sort()
        if not scenarios:
            print(f"No JSON scenario files found in directory: {path}")
            sys.exit(1)
    else:
        scenarios = [path]

    if args.internal_run:
        # Silence standard logging to only output clean results
        import logging

        logging.getLogger().setLevel(logging.ERROR)
        dur, actual_ticks = asyncio.run(run_benchmark(scenarios[0], args.ticks, args.warmup))
        print(f"{dur},{actual_ticks}")
    elif args.compare:
        ref1, ref2 = args.compare
        run_compare(ref1, ref2, scenarios, args.ticks, args.repeats, args.warmup, args.jit_only)
    else:
        # Single run benchmark on current directory
        for scenario_path in scenarios:
            print(f"\nRunning benchmark for {scenario_path}...")
            dur, actual_ticks = asyncio.run(run_benchmark(scenario_path, args.ticks, args.warmup))
            print(f"Ticks simulated: {actual_ticks}")
            print(f"Duration: {dur:.4f} seconds ({actual_ticks / dur:.2f} ticks/s)")
