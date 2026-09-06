# Technical Architecture Overview

This section details the software engineering and high-performance computing (HPC) architecture of the Plant-Herbivore Interaction & Defense Simulator (PHIDS).

---

## Core Chapters

* [System Architecture](system_architecture.md) - High-level system topology, Entity-Component-System (ECS) data arrays, double-buffering invariants, and FastAPI/HTMX service integration.
* [Engine Execution](engine_execution.md) - Sequential loop phases (`FlowField` $\to$ `Lifecycle` $\to$ `Interaction` $\to$ `Signaling` $\to$ `Telemetry`), Numba `@njit` JIT optimization rules, and spatial hashing.
* [Interfaces & UI](interfaces_and_ui.md) - Dynamic HTMX web dashboard, Jinja2 template rendering, real-time Canvas 2D/3D map visualizer, and scenario hot-reloading via `DraftService`.
* [Telemetry](telemetry.md) - Zarr replay buffer serialization, deterministic PRNG seed recording, zero-copy matrix playback, and Polars analytical export pipelines.
* [Testing Architecture](testing_architecture.md) - Comprehensive testing framework featuring unit, integration, mutation (`mutmut`), and performance benchmark (`pytest-benchmark`) regression gates.
* [Signaling Trigger Invariants](signaling_triggers.md) - Deterministic state machine specifications and mathematical trigger cascades.

---

## Future Prospects

* [GPU CUDA Acceleration Engine](future_prospects/gpu_cuda_acceleration.md) - Architecture for offloading 2D/3D reaction-diffusion PDE stencil solvers and airborne VOC advection to PyTorch and CUDA C++ GPU kernels.
