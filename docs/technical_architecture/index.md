---
type: technical_architecture
title: Technical Architecture Overview
status: active
version: 1.0
description: High-level overview of PHIDS software architecture, data-oriented ECS execution loops, HTMX dashboard interfaces, Zarr telemetry, and testing gates.
tags: [phids, ecs, architecture, hpc]
generated: { by: process:okf-updater, at: "2026-07-26T18:30:00Z" }
resources:
- docs/technical_architecture/system_architecture.md
- docs/technical_architecture/engine_execution.md
- docs/technical_architecture/interfaces_and_ui.md
- docs/technical_architecture/telemetry.md
- docs/technical_architecture/testing_architecture.md
---

# Technical Architecture Overview

This section details the software engineering and high-performance computing (HPC) architecture of the Plant-Herbivore Interaction & Defense Simulator (PHIDS).

---

## Core Chapters

* **[System Architecture](system_architecture.md)**: High-level system topology, Entity-Component-System (ECS) data arrays, double-buffering invariants, and FastAPI/HTMX service integration.
* **[Engine Execution](engine_execution.md)**: Sequential loop phases (`FlowField` $\to$ `Lifecycle` $\to$ `Interaction` $\to$ `Signaling` $\to$ `Telemetry`), Numba `@njit` JIT optimization rules, and spatial hashing.
* **[Interfaces & UI](interfaces_and_ui.md)**: Dynamic HTMX web dashboard, Jinja2 template rendering, real-time Canvas 2D/3D map visualizer, and scenario hot-reloading via `DraftService`.
* **[Telemetry](telemetry.md)**: Zarr replay buffer serialization, deterministic PRNG seed recording, zero-copy matrix playback, and Polars analytical export pipelines.
* **[Testing Architecture](testing_architecture.md)**: Comprehensive testing framework featuring unit, integration, mutation (`mutmut`), and performance benchmark (`pytest-benchmark`) regression gates.

---

## Future Prospects

* **[GPU CUDA Acceleration Engine](future_prospects/gpu_cuda_acceleration.md)**: Architecture for offloading 2D/3D reaction-diffusion PDE stencil solvers and airborne VOC advection to PyTorch and CUDA C++ GPU kernels.
