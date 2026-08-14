---
okf_version: "0.2"
type: Reference
title: PHIDS Documentation Overview
status: active
version: 1.0
description: Core landing page and abstract for the Plant-Herbivore Interaction
  & Defense Simulator (PHIDS) documentation.
tags: [phids, abstract, biological-model, ecs]
generated: {by: process:okf-updater, at: "2026-07-26T18:31:00Z"}
sources:
- resource: docs/scientific_model/index.md
- resource: docs/technical_architecture/index.md
- resource: docs/scenario_guide/index.md
- resource: docs/reference/index.md
---

<img src="assets/logo.png" align="right" width="200" alt="PHIDS Logo">

## Abstract

The evolutionary arms race between flora and their herbivores is a primary driver of terrestrial biodiversity. Plants, though sessile, are not passive victims of herbivory; they deploy a sophisticated array of constitutive and induced chemical defenses to deter feeding, inhibit digestion, or signal distress to neighboring foliage. In turn, herbivores evolve physiological tolerance, behavioral avoidance, and localized foraging strategies to bypass these botanical defenses.

The **Plant-Herbivore Interaction & Defense Simulator (PHIDS)** is a deterministic computational ecology instrument engineered to study these spatially localized trophic interactions. While classical ecological modeling often relies on perfectly mixed, continuous-time Ordinary Differential Equations (ODEs) like the Lotka-Volterra models, such abstractions fail to capture the critical heterogeneity of physical ecosystems. A herbivore's ability to locate a target, or a plant's ability to warn its neighbor via an underground fungal network, depends entirely on spatial context and temporal delays.

PHIDS bridges this gap by coupling a discrete, data-oriented Entity-Component-System (ECS) to simulate biological actors (swarms, plants) with continuous cellular automata fields to simulate atmospheric dispersion and biochemical gradient formation. It allows researchers to author, execute, and analyze reproducible experiments mapping how localized defensive strategies scale into macroscopic ecosystem stability or collapse.

## Biological Introduction

### The Limitations of Continuous Models

Traditional mathematical ecology models populations as continuous variables (e.g., $x$ foxes and $y$ rabbits) reacting instantly to one another. However, ecosystems are inherently noisy, discrete, and spatially fragmented. If a single plant begins synthesizing a lethal alkaloid, it only affects the herbivores actively feeding on its specific tissue. If that same plant releases an airborne Volatile Organic Compound (VOC) to warn neighboring flora, the efficacy of that warning is dictated by wind direction, diffusion rates, and the physical distance to the nearest compatible receiver.

### The PHIDS Model Scope

PHIDS is designed to investigate the complex, emergent phenomena that arise when these interactions are constrained to a physical grid. The simulator explicitly models:

* **Chemotactic Foraging:** Herbivore swarms do not possess omniscient knowledge of the ecosystem. They must navigate the terrain by sensing localized chemical gradients-moving toward areas of high caloric reward while actively avoiding dense concentrations of toxic or repellent compounds.
* **Constitutive vs. Induced Defenses:** Flora can possess baseline defenses (e.g., camouflage that masks their caloric gradient), but they can also deploy dynamic *induced* defenses. A plant may detect a minimum threshold of grazing pressure before synthesizing a targeted toxin or releasing an airborne alarm signal.
* **Reaction-Diffusion Mechanics:** Airborne signals (VOCs) are modeled using partial differential equations (PDEs), specifically isotropic Gaussian convolutions. This simulates how chemical plumes drift on the wind, decaying over time, and priming the defensive responses of down-wind flora before herbivores physically arrive.
* **Mycorrhizal Symbiosis:** Plants can form underground fungal networks. These root linkages allow for the instantaneous point-to-point transfer of chemical alarm signals, entirely bypassing atmospheric diffusion delays, but demanding high metabolic caloric upkeep from the participating plants.
* **Density-Dependent Population Dynamics:** Instead of simple starvation, herbivore swarms undergo continuous metabolic attrition, shrinking proportionately when caloric intake falls short of biological upkeep. Conversely, when grazing on dense, undefended flora, surplus energy drives rapid reproduction and macroscopic swarm mitosis (fracturing into new independent herds due to localized crowding).

By providing researchers with the ability to define distinct flora/herbivore species, map complex trigger networks (e.g., "If *Herbivore B* attacks, synthesize *Substance X*"), and dictate environmental conditions (wind, carrying capacity), PHIDS serves as a digital laboratory for investigating theoretical defensive strategies and stability thresholds.

---

## Core Simulation Principles (Technical Architecture)

PHIDS is engineered as a research-grade simulation backend. To ensure that ecological outputs are mathematically traceable and experimentally reproducible, the system adheres to strict architectural constraints:

* **OpenMP Multi-Threaded JIT Parallelization & FTZ Flushing:** Distributes grid row sweeps (`numba.prange()`) across CPU worker threads in Jacobi flow relaxation and signal diffusion (`@njit(parallel=True, fastmath=True)`), delivering $3\times - 6\times$ macro throughput gains while enforcing Flush-to-Zero (FTZ / DAZ) subnormal float elimination below `SIGNAL_EPSILON` ($1\times 10^{-4}$).
* **Charnov MVT Foraging Kinetics & Softmax Selection (Planned Stage 1B Specification):** Formal design specification for continuous spatial potential re-evaluation and Boltzmann stochastic action selection ($P(\text{move}) = \frac{\exp(F/\tau)}{\sum \exp(F/\tau)}$) to model patch departure prior to total resource depletion.
* **Deterministic Multi-Scale Phase-Staggered Cohort Execution** through `SimulationLoop.step()`. Evaluates fast physical processes (VOC diffusion, micro-chemotaxis) on every tick, while daily metabolism ($24\times$ stride) and plant growth/mycorrhiza/reproduction ($168\times$ weekly stride) execute via phase-staggered entity cohorts (`(entity_id % S) == (tick % S)`). This eliminates subnormal IEEE 754 float truncation traps ($<10^{-4}$) and macro telemetry sawtooth spikes while preserving uniform L1/L2 cache locality.
* **$O(1)$ Stochastic Raycasting Dispersal** replacing $O(N \times r^2)$ spatial matrix convolution. Seeds project along advective wind unit vectors $\mathbf{u}$ with single-axis turbulent Gaussian scatter $\delta_\perp \sim \mathcal{N}(0, \sigma_\perp^2)$ in constant time.
* **Data-oriented state storage** utilizing an `ECSWorld` to manage biological entities and pre-allocated NumPy array buffers to manage continuous environmental fields.
* **Global flow-field navigation** instead of independent agent pathfinding. A unified scalar gradient is calculated via Numba JIT compilation, which swarms sample locally.
* **Double-buffered environmental updates** for diffusion layers to prevent intra-tick read-after-write contamination.
* **256-Bit AVX2 SIMD & Numba JIT Kernels:** High-throughput performance kernels (diet matrix anchoring `_is_swarm_anchored_jit`, energy layer reduction `rebuild_energy_layer`, 168-hour biomass growth `_grow_simd_jit`, mycorrhizal tax deduction `_apply_mycorrhizal_tax_jit`, in-place VOC decay `_numba_decay_signal_layer`, spatial hash `EMPTY_SET` singleton set reuse, active channel bitmasking `active_mask & (1 << s)`, and pre-compiled foraging parameter caching `CachedFloraForagingParams`/`CachedHerbivoreForagingParams`) execute across 256-bit YMM registers with zero heap allocation churn.
* **$O(1)$ spatial locality queries** through a Spatial Hash, bypassing catastrophic $O(N^2)$ distance polling.

These are not incidental implementation details; they define the simulator's methodological scope and ensure its high-performance computational efficiency.

### Legacy Simulation Invariants

During the migration from legacy Object-Oriented implementations to the current data-oriented framework, several core operational invariants were formalized:

1. **$O(1)$ Spatial Lookups:**
    * *Legacy limitation:* Calculating Euclidean distance between every swarm and every plant created severe CPU bottlenecks.
    * *Current invariant:* All locational biology (feeding, reproduction boundaries, toxin triggering) is resolved through an `ECSWorld` Spatial Hash mapping $(x, y)$ coordinates directly to Entity IDs.
2. **No Dynamic Array Allocation (The Rule of 16):**
    * *Legacy limitation:* Growing interaction matrices dynamically caused memory latency.
    * *Current invariant:* The ecosystem is strictly bounded. At initialization, 16 flora, 16 herbivores, and 16 substance profiles are pre-allocated.
3. **Subnormal Float Clamping:**
    * *Legacy limitation:* Diffusing signal clouds created infinitely long decimal tails (e.g., `1e-300`), which crash processor FPUs.
    * *Current invariant:* Any continuous signal concentration dropping below $\varepsilon$ (`1e-4`) is explicitly truncated to `0.0`.
4. **No Homogeneous Continuous Fractions:**
    * *Legacy limitation:* Simple ODE solvers allow for 0.43 of a swarm to exist, failing to map to spatial grids.
    * *Current invariant:* Swarms suffer fractional deficit attrition internally, but split boundaries and final spatial placement are resolved through discrete, physical Entity components.

## Current Runtime Anchors

* `phids.engine.loop.SimulationLoop` - orchestrates the ordered simulation phases.
* `phids.engine.core.biotope.GridEnvironment` - owns vectorized environmental layers.
* `phids.engine.core.ecs.ECSWorld` - stores entities and spatial-locality data.
* `phids.api.ui_state.DraftState` - holds editable UI state before live loading.
* `phids.telemetry.analytics.TelemetryRecorder` - records tick-level output metrics.

## Documentation Map

* **Scientific Model** - research scope, detailed breakdown of mathematical models (Chemotaxis, PDEs), biological reasoning, and equations:
    * [Scientific Model](scientific_model/mathematical_framework.md)
* **Technical Architecture** - system constraints, package boundaries, loop ownership, interfaces, and telemetry:
    * [Testing Architecture](technical_architecture/testing_architecture.md)
    * [Technical Architecture](technical_architecture/system_architecture.md)
* **Scenarios** - schema semantics, import/export, and curated examples:
    * [Evolutionary Encapsulated Multi-Stage Design Space Exploration (EEDSE)](scenario_guide/design_space_exploration.md)
    * [Agentic Diagnostic Log Writer](scenario_guide/future_prospects/agentic_log_writer.md)
    * [Scenario Guide](scenario_guide/scenario_authoring.md)
* **Development & Reference** - API Reference, contribution workflows, agent orchestration (MCP & AITL Diagnostic Observers), and historical archives:
    * [Development Guide](development_guide/contribution_workflow.md)

## How to Read This Site

For initial onboarding, the recommended reading progression is:

1. Start with the deep dives in the [Scientific Model](scientific_model/mathematical_framework.md), especially [Chemotaxis & Flow Fields](scientific_model/chemotaxis.md) and [Reaction-Diffusion PDEs](scientific_model/reaction_diffusion.md).
2. Continue to the architecture overview under [Technical Architecture](technical_architecture/system_architecture.md).
3. Inspect the UI and REST surfaces in [Interfaces and UI](technical_architecture/interfaces_and_ui.md).
4. Review scenario authoring rules in [Scenario Guide](scenario_guide/scenario_authoring.md).

## Build and Serve the Documentation Locally

Build only:

```bash
just docs
```

Build and serve the documentation at `http://localhost:9000`:

```bash
just serve
```
