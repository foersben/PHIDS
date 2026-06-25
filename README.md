# 🌿 Plant-Herbivore Interaction & Defense Simulator (PHIDS)

PHIDS is a high-performance, deterministic ecological simulation framework for analyzing spatial trophic interactions, population dynamics, and chemically mediated defenses across discrete and continuous environments.

[![Python Version](https://img.shields.io/badge/python-3.13%2B-blue.svg)](https://www.python.org/downloads/)
[![Build Status](https://github.com/foersben/PHIDS/actions/workflows/ci.yml/badge.svg)](https://github.com/foersben/PHIDS/actions)
[![Coverage Status](https://coveralls.io/repos/github/foersben/PHIDS/badge.svg)](https://coveralls.io/github/foersben/PHIDS)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Live Documentation:** <https://foersben.github.io/PHIDS/>

---

## 🔬 Overview

The evolutionary arms race between flora and their herbivorous predators is a primary driver of terrestrial biodiversity. While plants are sessile, they are far from defenseless; they deploy a sophisticated array of constitutive and induced chemical defenses to deter feeding, inhibit digestion, or signal distress to neighboring foliage. Herbivores, in turn, evolve physiological tolerance, behavioral avoidance, and localized foraging strategies to bypass these defenses.

PHIDS bridges the gap between biological theory and computational simulation. Traditional ecological models often rely on perfectly mixed, continuous-time equations that fail to capture the spatial fragmentation and temporal delays inherent in physical ecosystems. A predator's ability to locate a target, or a plant's ability to warn its neighbor via airborne volatiles, depends entirely on physical distance and environmental mechanics.

By coupling a discrete, data-oriented **Entity-Component-System (ECS)** with continuous cellular automata fields, PHIDS allows researchers, ecologists, and software engineers to author, execute, and analyze reproducible experiments, mapping how localized, organism-level defensive strategies scale into macroscopic ecosystem stability or collapse.

---

## 🧬 Scientific Model

PHIDS models complex, emergent ecological phenomena by constraining trophic interactions to a physical grid. The core biological mechanics driving the simulation include:

### Lotka-Volterra Population Dynamics
At its foundation, PHIDS models the classic predator-prey relationship described by Lotka-Volterra dynamics, but translates these principles from theoretical, perfectly-mixed populations into a discrete, spatially-aware environment. Herbivores must actively seek out plants to consume caloric energy for survival and reproduction. Plants, in turn, accumulate energy through photosynthesis. Population scaling is driven by this strict, spatially-dependent metabolic accounting, leading to localized booms, crashes, and persistent oscillation patterns.

### Reaction-Diffusion & Chemical Signaling
Rather than assuming instant global communication, PHIDS utilizes continuous reaction-diffusion fields (coupled with semi-Lagrangian advection for local wind effects) to model the spread of biochemical compounds. Plants can synthesize airborne Volatile Organic Compounds (VOCs) to warn neighboring flora of herbivore pressure, or transmit distress signals via underground mycorrhizal networks. The dispersion of these signals is bound by physical diffusion rates, decay coefficients, and environmental factors, ensuring that ecological communication remains localized and delayed.

### Chemotactic Foraging & Trophic Defenses
Herbivores in PHIDS do not possess omniscient knowledge of the map. They forage via chemotaxis—sensing and navigating localized chemical gradients to find caloric rewards while avoiding toxic compounds. Plants can counter this by deploying both baseline (constitutive) defenses, like camouflage that masks their caloric signature, and reactive (induced) defenses. When grazing pressure reaches a threshold, a plant might synthesize a targeted toxin or release an alarm signal, triggering compound chemical-defense cascades across the ecosystem.

---

## ⚙️ Technical Architecture

Following recent massive architectural sweeps (Phases 1-4), PHIDS is engineered for uncompromised performance, strict data integrity, and determinism. It serves both the ecological researcher demanding precision and the MLOps engineer requiring high-throughput data pipelines.

### Engine: ECS, Numba JIT & Deterministic Double-Buffering
The simulation core is built around a data-oriented **Entity Component System (ECS)** in pure Python, aggressively accelerated by **Numba JIT** compilation.
* **Strict Phase Sequence & Double-Buffering:** To ensure exact determinism and reproducibility, the engine executes a strict phase sequence (flow field -> lifecycle -> interaction -> signaling -> telemetry/termination). Grid updates rely on explicit read/write double-buffering (Phase 6 Buffer Swaps) to prevent race conditions during continuous diffusion processes.
* **Fast-Path Heuristics:** The ECS employs $O(1)$ fast-path optimizations, such as the "Anchoring Heuristic", which bypasses costly flow-field pathfinding for swarms currently positioned on food sources, drastically reducing CPU overhead during grazing events.
* **Rule of 16:** The spatial `GridEnvironment` enforces fixed memory allocations (maximum 16 species/substances) to ensure predictable $L1/L2$ cache utilization and invariant execution times.

### API Ingress: Strict Data Boundaries with Pydantic V2
Legacy `Any` types and defensive type-coercion shims have been completely eradicated. The FastAPI boundary is guarded by strict **Pydantic V2** schemas. All scenario configurations, species parameters, and chemical-defense cascades are comprehensively validated mathematically before data ever reaches the simulation engine, ensuring a pure state runtime.

### UI & WebSockets: FastAPI, HTMX & TailwindCSS
The web-based control center is served by **FastAPI**, rendered via server-side templates with **HTMX**, and styled using **Tailwind CSS**. To allow the UI to render massive swarms and grids effortlessly, the WebSocket telemetry streams (`/ws/ui/stream`) utilize strictly columnar JSON payloads with cache signatures, entirely preventing redundant encoding overhead.

### Telemetry & Export: High-Performance Zarr
Moving away from legacy `msgpack`, PHIDS now defaults to the **Zarr** storage backend for replay data and telemetry exports. This enables high-performance, chunked, and memory-decoupled visual slicing of long-running Monte Carlo batch simulations. Analysts can load enormous datasets into **Polars** or Pandas DataFrames seamlessly without memory exhaustion.

### Agentic Integration: MCP Server Support
PHIDS is natively designed to be operated by AI agents. A specialized, stdio-based **Model Context Protocol (MCP)** server (`src/phids/mcp_server.py`) is included. It allows external LLMs and agents to hook directly into the simulator to safely read the `runtime_snapshot()` (scenario metadata, species counts) and query `recent_logs()`, enabling autonomous scenario tuning, diagnostic debugging, and experiment generation.

---

## 🚀 Quickstart & Installation

PHIDS requires Python 3.13 or higher. Dependency management and environment isolation are handled by [Astral's `uv`](https://github.com/astral-sh/uv), and task execution is automated via [`just`](https://github.com/casey/just).

### Prerequisites
1. Install `uv`: `curl -LsSf https://astral.sh/uv/install.sh | sh`
2. Install `just`: `cargo install just` (or via your system package manager)

### Local Setup
Clone the repository and run the setup command, which will sync all dependencies, set up the virtual environment, and install pre-commit hooks:

```bash
git clone https://github.com/foersben/PHIDS.git
cd PHIDS
just setup
```

### Running the Simulator
To launch the FastAPI HTTP server, HTMX frontend UI, and WebSocket simulation streams:

```bash
just run
```
Access the UI via your browser at **http://127.0.0.1:8000**.

If you need to bypass `just`, you can run the server directly via `uv`:
```bash
uv run phids
```

---

## 🛠️ Development & Testing

We enforce strict quality gates to guarantee arithmetic invariants and simulation stability.

### Two-Pass Numba Testing Strategy
The ECS engine relies heavily on Numba JIT compilation. To ensure both logical correctness and memory-safe machine code generation, our CI pipeline employs a strict two-pass testing strategy:
1. **Pass 1: Logic & Coverage:** Tests are run with `NUMBA_DISABLE_JIT=1` to enforce pure-Python line coverage and validate branch logic without compilation overhead.
2. **Pass 2: Compilation Verification:** Tests are re-run with JIT enabled to verify safe machine-code compilation and ensure zero runtime segfaults.

### Property Hypothesis Testing
To guarantee invariant ecosystem rules (e.g., mass conservation, correct condition tree algebraic evaluation), PHIDS utilizes property-based testing (via the `hypothesis` library). These pilot tests aggressively explore edge cases in interaction logic.

### Useful `just` Commands
- `just test`: Run the full test suite via pytest.
- `just lint`: Automatically fix formatting and run static analysis (Ruff & Mypy).
- `just check`: Run all pre-commit hooks across the codebase.
- `just docs`: Build and serve the Zensical documentation strictly.
- `just clean`: Remove all build artifacts, cache directories, and test coverage files.

You can also run tests explicitly via `uv`: `uv run pytest`.

---

## 📂 Project Layout

The repository is modularly structured to strictly separate the deterministic simulation loop from API side-effects.

```text
PHIDS/
├── src/phids/
│   ├── api/            # FastAPI routes, Pydantic schemas, and HTMX templates
│   ├── engine/         # The core determinism domain
│   │   ├── core/       # ECS architecture and biotope grid fields
│   │   ├── systems/    # Biological mechanics (lifecycle, grazing, diffusion)
│   │   └── loop.py     # The primary Phase-sequenced SimulationLoop
│   ├── io/             # High-performance Zarr replays and scenario parsing
│   ├── telemetry/      # Tick analytics, export routines, and Polars handlers
│   ├── shared/         # Common utilities and logging configurations
│   └── mcp_server.py   # Model Context Protocol stdio entrypoint for AI Agents
├── tests/              # Property-based invariant tests and API integration tests
├── docs/               # Scientific model specifications and technical architecture
├── pyproject.toml      # Dependency and metadata configuration (requires >=3.13)
└── Justfile            # Command runner definitions for CI and local development
```

---

## 📜 License & Contributing

PHIDS is open-source software licensed under the [MIT License](LICENSE).

Contributions from ecologists, mathematicians, and software engineers are highly encouraged! Please ensure all pull requests pass the `just lint` and two-pass `just test` quality gates before submission.
