---
okf_version: "0.2"
type: Reference
title: PHIDS Documentation Overview
status: stable
stale_after: "2027-01-01"
version: 1.0
description: Core landing page and abstract for the Plant-Herbivore Interaction
  & Defense Simulator (PHIDS) documentation.
tags: [phids, abstract, biological-model, ecs]
generated: {by: process:okf-updater, at: "2026-07-26T18:31:00Z"}
verified: {by: process:okf-updater, at: "2026-08-14T16:00:00Z"}
sources:
- id: index
  resource: docs/scientific_model/index.md
- id: technical_architecture_index
  resource: docs/technical_architecture/index.md
- id: scenario_guide_index
  resource: docs/scenario_guide/index.md
- id: reference_index
  resource: docs/reference/index.md
---

<img src="assets/logo.png" align="right" width="200" alt="PHIDS Logo">

## Abstract

The evolutionary arms race between flora and their herbivores is a primary driver of terrestrial biodiversity. Plants, though sessile, are not passive victims of herbivory; they deploy a sophisticated array of constitutive and induced chemical defenses to deter feeding, inhibit digestion, or signal distress to neighboring foliage. In turn, herbivores evolve physiological tolerance, behavioral avoidance, and localized foraging strategies to bypass these botanical defenses.

The **Plant-Herbivore Interaction & Defense Simulator (PHIDS)** is a stochastically reproducible computational ecology instrument engineered to study these spatially localized trophic interactions. While classical ecological modeling often relies on perfectly mixed, continuous-time Ordinary Differential Equations (ODEs) like the Lotka-Volterra models, such abstractions fail to capture the critical heterogeneity of physical ecosystems. A herbivore's ability to locate a target, or a plant's ability to warn its neighbor via an underground fungal network, depends entirely on spatial context and temporal delays.

PHIDS bridges this gap by coupling a discrete, data-oriented Entity-Component-System (ECS) to simulate biological actors (swarms, plants) with grid-based scalar concentration fields to simulate atmospheric dispersion and biochemical gradient formation. It allows researchers to author, execute, and analyze reproducible experiments mapping how localized defensive strategies scale into macroscopic ecosystem stability or collapse.

## Biological Introduction

### The Limitations of Continuous Models

Traditional mathematical ecology models populations as continuous variables (e.g., $x$ foxes and $y$ rabbits) reacting instantly to one another. However, ecosystems are inherently noisy, discrete, and spatially fragmented. If a single plant begins synthesizing a lethal alkaloid, it only affects the herbivores actively feeding on its specific tissue. If that same plant releases an airborne Volatile Organic Compound (VOC) to warn neighboring flora, the efficacy of that warning is dictated by wind direction, diffusion rates, and the physical distance to the nearest compatible receiver.

### The PHIDS Model Scope

PHIDS is designed to investigate the complex, emergent phenomena that arise when these interactions are constrained to a physical grid. The simulator explicitly models:

* **Chemotactic Foraging:** Herbivore swarms do not possess omniscient knowledge of the ecosystem. They must navigate the terrain by sensing localized chemical gradients-moving toward areas of high caloric reward while actively avoiding dense concentrations of toxic or repellent compounds.
* **Constitutive vs. Induced Defenses:** Flora can possess baseline defenses (e.g., camouflage that masks their caloric gradient), but they can also deploy dynamic *induced* defenses. A plant may detect a minimum threshold of grazing pressure before synthesizing a targeted toxin or releasing an airborne alarm signal.
* **Reaction-Diffusion Mechanics:** Airborne signals (VOCs) are modeled using partial differential equations (PDEs), specifically isotropic Gaussian convolutions. This simulates how chemical plumes drift on the wind (with freely configurable wind direction and magnitude), decaying over time, and priming the defensive responses of down-wind flora before herbivores physically arrive.
* **Mycorrhizal Symbiosis:** Plants can form underground fungal networks. These root linkages allow for the instantaneous network-wide signal propagation of chemical alarm signals, entirely bypassing atmospheric diffusion delays, but demanding high metabolic caloric upkeep from the participating plants.
* **Density-Dependent Population Dynamics:** Instead of simple starvation, herbivore swarms undergo continuous metabolic attrition, shrinking proportionately when caloric intake falls short of biological upkeep. Conversely, when grazing on dense, undefended flora, surplus energy drives rapid reproduction and macroscopic swarm mitosis (fracturing into new independent herds due to localized crowding).

By providing researchers with the ability to define distinct flora/herbivore species, map complex trigger networks (e.g., "If *Herbivore B* attacks, synthesize *Substance X*"), and dictate environmental conditions (wind, carrying capacity), PHIDS serves as a digital laboratory for investigating theoretical defensive strategies and stability thresholds.

---

## Core Simulation Principles (Technical Architecture)

PHIDS is engineered as a research-grade simulation backend. To ensure that ecological outputs are mathematically traceable and experimentally reproducible, the system adheres to strict architectural constraints:

* **Massive Scale Execution (JIT & SIMD):** By utilizing 256-bit AVX2 SIMD instructions and Numba JIT compilation for core environmental kernels, PHIDS executes heavy calculations across CPU registers with zero heap allocation churn.
* **Parallel Processing & Float Truncation (FTZ):** Grid sweeps (like signal diffusion) are distributed across multi-threaded CPU workers. To prevent processor stalls caused by infinitely long decimal tails in decaying signal clouds, the engine enforces strict Flush-to-Zero (FTZ) subnormal float elimination.
* **Advanced Foraging Kinetics (Charnov MVT):** Formal design specifications ensure swarms make stochastic, biologically plausible decisions about when to abandon a depleting resource patch, rather than eating it perfectly down to zero.
* **Phase-Staggered Cohort Execution:** Heavy biological processes (like growth and reproduction) are temporally staggered across different time slices (cohorts taking turns). This prevents massive CPU spikes that would occur if all entities tried to reproduce or grow on the exact same tick.
* **Constant-Time Dispersal ($O(1)$ Stochastic Raycasting):** Instead of calculating wind drift for every single cell in a massive grid, seeds and signals project along wind vectors in constant time, vastly accelerating the simulation of advective weather patterns.
* **Predictable Ecosystem Scaling (Data-Oriented Storage):** By pre-allocating contiguous NumPy array buffers for environment fields and using an Entity-Component-System (ECS) for biological actors, the engine guarantees memory locality and prevents garbage collection pauses.
* **Global Flow-Field Navigation:** Rather than expensive, independent pathfinding for every animal, a unified scalar gradient is calculated globally, which swarms sample locally.
* **Double-buffered Environmental Updates:** Ensures deterministic read/write safety for diffusion layers, preventing intra-tick contamination.
* **Instant Spatial Locality Queries:** Utilizes a Spatial Hash map to instantly locate nearby flora or herbivores without catastrophic $O(N^2)$ distance polling.

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
    * *Legacy limitation:* Traditional continuous mathematical equations can result in physically impossible fractions of animals (e.g., calculating that 0.43 of a rabbit survived), which fails to map onto a physical, discrete grid.
    * *Current invariant:* PHIDS enforces discrete, whole physical entities. While swarms track internal caloric deficits as floats, their physical existence and splitting boundaries are absolute integers on the grid.

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
