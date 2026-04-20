# PHIDS: Plant-Herbivore Interaction & Defense Simulator

## Abstract

The evolutionary arms race between flora and their herbivorous predators is a primary driver of terrestrial biodiversity. Plants, though sessile, are not passive victims of predation; they deploy a sophisticated array of constitutive and induced chemical defenses to deter feeding, inhibit digestion, or signal distress to neighboring foliage. In turn, herbivores evolve physiological tolerance, behavioral avoidance, and localized foraging strategies to bypass these botanical defenses.

The **Plant-Herbivore Interaction & Defense Simulator (PHIDS)** is a deterministic computational ecology instrument engineered to study these spatially localized trophic interactions. While classical ecological modeling often relies on perfectly mixed, continuous-time Ordinary Differential Equations (ODEs) like the Lotka-Volterra models, such abstractions fail to capture the critical heterogeneity of physical ecosystems. A predator’s ability to locate a target, or a plant's ability to warn its neighbor via an underground fungal network, depends entirely on spatial context and temporal delays.

PHIDS bridges this gap by coupling a discrete, data-oriented Entity-Component-System (ECS) to simulate biological actors (swarms, plants) with continuous cellular automata fields to simulate atmospheric dispersion and biochemical gradient formation. It allows researchers to author, execute, and analyze reproducible experiments mapping how localized defensive strategies scale into macroscopic ecosystem stability or collapse.

## Biological Introduction

### The Limitations of Continuous Models
Traditional mathematical ecology models populations as continuous variables (e.g., $x$ foxes and $y$ rabbits) reacting instantly to one another. However, ecosystems are inherently noisy, discrete, and spatially fragmented. If a single plant begins synthesizing a lethal alkaloid, it only affects the herbivores actively feeding on its specific tissue. If that same plant releases an airborne Volatile Organic Compound (VOC) to warn neighboring flora, the efficacy of that warning is dictated by wind direction, diffusion rates, and the physical distance to the nearest compatible receiver.

### The PHIDS Model Scope
PHIDS is designed to investigate the complex, emergent phenomena that arise when we constrain these interactions to a physical grid. The simulator explicitly models:

*   **Chemotactic Foraging:** Herbivore swarms do not possess omniscient knowledge of the ecosystem. They must navigate the terrain by sensing localized chemical gradients—moving toward areas of high caloric reward while actively avoiding dense concentrations of toxic or repellent compounds.
*   **Constitutive vs. Induced Defenses:** Flora can possess baseline defenses (e.g., camouflage that masks their caloric gradient), but they can also deploy dynamic *induced* defenses. A plant may detect a minimum threshold of grazing pressure before synthesizing a targeted toxin or releasing an airborne alarm signal.
*   **Reaction-Diffusion Mechanics:** Airborne signals (VOCs) are modeled using partial differential equations (PDEs), specifically isotropic Gaussian convolutions. This simulates how chemical plumes drift on the wind, decaying over time, and priming the defensive responses of down-wind flora before herbivores physically arrive.
*   **Mycorrhizal Symbiosis:** Plants can form underground fungal networks. These root linkages allow for the instantaneous point-to-point transfer of chemical alarm signals, entirely bypassing atmospheric diffusion delays, but demanding high metabolic caloric upkeep from the participating plants.
*   **Density-Dependent Population Dynamics:** Instead of simple starvation, herbivore swarms undergo continuous metabolic attrition, shrinking proportionately when caloric intake falls short of biological upkeep. Conversely, when grazing on dense, undefended flora, surplus energy drives rapid reproduction and macroscopic swarm mitosis (fracturing into new independent herds due to localized crowding).

By providing researchers with the ability to define distinct flora/herbivore species, map complex trigger networks (e.g., "If *Herbivore B* attacks, synthesize *Substance X*"), and dictate environmental conditions (wind, carrying capacity), PHIDS serves as a digital laboratory for investigating theoretical defensive strategies and stability thresholds.

---

## Core Simulation Principles (Technical Architecture)

PHIDS is engineered as a research-grade simulation backend. To ensure that ecological outputs are mathematically traceable and experimentally reproducible, the system adheres to strict architectural constraints:

- **Deterministic tick ordering** through `SimulationLoop.step()`. Given the same configuration, the simulation will yield the exact same tick-by-tick trajectory.
- **Data-oriented state storage** utilizing an `ECSWorld` to manage biological entities and pre-allocated NumPy array buffers to manage continuous environmental fields.
- **Global flow-field navigation** instead of independent agent pathfinding. A unified scalar gradient is calculated via Numba JIT compilation, which swarms sample locally.
- **Double-buffered environmental updates** for diffusion layers to prevent intra-tick read-after-write contamination.
- **Rule-of-16 bounded configuration spaces** for species and substances to prevent dynamic memory allocation latency during the hot execution loop.
- **O(1) spatial locality queries** through a Spatial Hash, bypassing catastrophic $O(N^2)$ distance polling.

These are not incidental implementation details; they define the simulator's methodological scope and ensure its high-performance computational efficiency.

### Legacy Simulation Invariants

During the migration from legacy Object-Oriented implementations to the current data-oriented framework, several core operational invariants were formalized:

1.  **$O(1)$ Spatial Lookups:**
    *Legacy limitation:* Calculating Euclidean distance between every swarm and every plant created severe CPU bottlenecks.
    *Current invariant:* All locational biology (feeding, reproduction boundaries, toxin triggering) is resolved through an `ECSWorld` Spatial Hash mapping $(x, y)$ coordinates directly to Entity IDs.
2.  **No Dynamic Array Allocation (The Rule of 16):**
    *Legacy limitation:* Growing interaction matrices dynamically caused memory latency.
    *Current invariant:* The ecosystem is strictly bounded. At initialization, 16 flora, 16 herbivores, and 16 substance profiles are pre-allocated.
3.  **Subnormal Float Clamping:**
    *Legacy limitation:* Diffusing signal clouds created infinitely long decimal tails (e.g., `1e-300`), which crash processor FPUs.
    *Current invariant:* Any continuous signal concentration dropping below $\varepsilon$ (`1e-4`) is explicitly truncated to `0.0`.
4.  **No Homogeneous Continuous Fractions:**
    *Legacy limitation:* Simple ODE solvers allow for 0.43 of a swarm to exist, failing to map to spatial grids.
    *Current invariant:* Swarms suffer fractional deficit attrition internally, but split boundaries and final spatial placement are resolved through discrete, physical Entity components.

## Current Runtime Anchors

- `phids.engine.loop.SimulationLoop` — orchestrates the ordered simulation phases.
- `phids.engine.core.biotope.GridEnvironment` — owns vectorized environmental layers.
- `phids.engine.core.ecs.ECSWorld` — stores entities and spatial-locality data.
- `phids.api.ui_state.DraftState` — holds editable UI state before live loading.
- `phids.telemetry.analytics.TelemetryRecorder` — records tick-level output metrics.

## Documentation Map

- **Scientific Model** — research scope, detailed breakdown of mathematical models (Chemotaxis, PDEs), biological reasoning, and equations:
  [`scientific_model/`](scientific_model/mathematical_framework.md)
- **Technical Architecture** — system constraints, package boundaries, loop ownership, interfaces, and telemetry:
  [`technical_architecture/`](technical_architecture/system_architecture.md)
- **Scenarios** — schema semantics, import/export, and curated examples:
  [`scenario_guide/`](scenario_guide/scenario_authoring.md)
- **Development & Reference** — API Reference, contribution workflows, agent orchestration (MCP), and historical archives:
  [`development_guide/`](development_guide/contribution_workflow.md)

## How to Read This Site

If you are new to the project, a practical reading order is:

1. Start with the deep dives in the [`scientific_model/`](scientific_model/mathematical_framework.md), especially [Chemotaxis & Flow Fields](scientific_model/chemotaxis.md) and [Reaction-Diffusion PDEs](scientific_model/reaction_diffusion.md).
2. Continue to the architecture overview under [`technical_architecture/system_architecture.md`](technical_architecture/system_architecture.md).
3. Inspect the UI and REST surfaces in [`technical_architecture/interfaces_and_ui.md`](technical_architecture/interfaces_and_ui.md).
4. Review scenario authoring rules in [`scenario_guide/scenario_authoring.md`](scenario_guide/scenario_authoring.md).

## Build the Documentation Locally

```bash
uv sync --all-extras --dev
uv run mkdocs serve
```
