---
type: roadmap
title: Strategic Development & Scientific Roadmap
status: active
version: 1.0
description: Strategic multi-phase development roadmap for PHIDS, detailing biological fidelity milestones and high-performance computing capabilities.
tags:
- phids
- roadmap
- architecture
- biological-fidelity
- hpc
timestamp: "2026-07-25T18:55:00Z"
resources:
- docs/scientific_model/index.md
- docs/technical_architecture/system_architecture.md
- docs/scenario_guide/design_space_exploration.md
---

# Strategic Development & Scientific Roadmap

This document outlines the multi-phase strategic development roadmap for the Plant-Herbivore Interaction & Defense Simulator (PHIDS). It defines milestones from both **biological fidelity** and **high-performance computing (HPC)** perspectives.

---

## Phase 1: High-Performance Engine & Core Biological Upgrades (v1.0 - Current)

### Biological Milestones
* **Continuous Sigmoidal Hill Priming**: Transitioned plant VOC perception from crude step-functions to dose-dependent logarithmic Hill kinetics ($S(c) = \frac{c^n}{K^n + c^n}$).
* **Rate-Limited Phloem Translocation**: Modeled vascular carbohydrate movement from leaves to roots ($\frac{dN}{dt} = -k(N - N_{\text{target}})$), establishing biological vulnerability windows.
* **Constitutive Morphological Defenses**: Integrated mechanical mouthpart damage ($\lfloor m_{\text{bite}} (1-\rho) \rfloor$) and cell-wall caloric discounting ($\eta_{\text{net}}$).
* **Mycorrhizal Carbon Tax**: Applied continuous photosynthate maintenance fees to root-fungal networks.
* **Holling Type II Response & Swarm Paradigms**: Implemented saturating feeding curves incorporating handling time $T_h$ and multi-tier flight behavior (`MACRO_SWARM`, `SOLITARY_GRAZER`, `OVIPOSITION_SEEKER`).

### Computer Science & Mathematical Milestones
* **Data-Oriented ECS Architecture**: Unified discrete entity spatial hashing with zero-allocation JIT execution loops.
* **JIT-Accelerated Flow Fields**: Parallelized potential surface calculations ($F = \alpha E \cdot N - \beta \sum T_k$) via Numba `@njit(parallel=True)`.
* **Operator-Splitting PDE Solvers**: Combined semi-Lagrangian wind advection with $3\times 3$ isotropic Gaussian convolution stencils and float denormalization clamps ($<10^{-4} \to 0.0$).
* **Zarr Telemetry Replay & HTMX UI**: Enabled deterministic tick-by-tick binary replay and live web dashboard monitoring.

---

## Phase 2: Advanced Spatial Fidelity & 3D Micro-Climate Extensions (v2.0 - Planned)

### Biological Milestones
* **3D Vertical Canopy Structure**: Extend atmospheric VOC diffusion to 3D grid layers, modeling height-dependent wind shear, canopy boundary layers, and vertical thermal convection.
* **Dynamic Subterranean Mycorrhizal Growth**: Evolve static graph links into dynamic root hyphae growth models governed by soil nutrient gradients and soil moisture.
* **Oviposition & Life-Stage Kinetics**: Implement multi-stage insect development (egg incubation, larval grazing stages, adult flight dispersal).

### Computer Science & Mathematical Milestones
* **3D Stencil Acceleration**: Extend Numba JIT kernels to 3D spatial arrays ($W \times H \times Z$) with SIMD vectorization.
* **Sparse Hyphae Graph Solvers**: Integrate sparse linear algebra routines for dynamic graph network propagation without dense matrix overhead.
* **Distributed Telemetry Streaming**: Stream Zarr chunked arrays over WebSocket protocols to remote visualization clients without memory thrashing.

---

## Phase 3: Distributed HPC Execution & AI-Driven Ecosystem Optimization (v3.0 - Future Vision)

### Biological Milestones
* **Multi-Habitat Landscape Connectivity**: Connect disparate biotope patches via migration corridors to simulate macro-ecological landscape dynamics and invasive species corridors.
* **Coevolutionary Game Theory**: Model multi-generational plant-herbivore coevolution, discovering optimal defense investment strategies under climate stress.

### Computer Science & Mathematical Milestones
* **GPU-Accelerated PyTorch/CUDA PDE Engines**: Port cellular automata reaction-diffusion layers to GPU tensor accelerators for million-cell biotopes.
* **AI Agent Design Space Exploration (DSE)**: Automate Pareto multi-objective optimization using reinforcement learning agents to discover non-dominated ecological trade-offs.
