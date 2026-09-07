# Development Guide Overview

This section outlines the software engineering principles, development workflows, quality assurance gates, and automated architectural paradigms governing the Plant-Herbivore Interaction & Defense Simulator (PHIDS).

## Engineering Philosophy & System Constraints

PHIDS is engineered as a zero-allocation, high-performance hybrid dynamical simulator. High computational throughput and physical fidelity are maintained through strict design constraints:

* **Data-Oriented ECS Architecture**: Behavioral state is stored exclusively in contiguous NumPy component arrays, eliminating object-oriented overhead in simulation hot paths.
* **Double-Buffered State Mutation**: All grid environments and entity systems read strictly from current layers and write updates exclusively to isolated write buffers, preventing intra-tick race conditions and order-dependent execution bias.
* **SIMD-Optimized Kernels**: Mathematical operations and field dynamics are JIT-compiled with Numba `@njit(parallel=True, fastmath=True)`, with Python objects strictly prohibited within compiled inner loops.
* **Deterministic Replay Integrity**: Every stochastic branch and deterministic state shift is recorded into Zarr replay buffers, allowing exact post-hoc analysis and bit-accurate playback without re-evaluating engine logic.

## Components of the Development Guide

* [Strategic Roadmap](roadmap.md) - Multi-stage development roadmap across pre-v1.0 foundational milestones, empirical bio-database integration, and long-term research horizons.
* [Contribution & Workflows](contribution_workflow.md) - Engineering standards, two-pass Numba testing protocol, pre-commit quality gates, and release management runbooks.
* [Agent Ecosystem](agent_ecosystem.md) - Autonomous agent personas, specialized IDE roles, MCP server introspection tools, and AITL diagnostic logging pipelines.
* [OKF Data-Flow Matrix Architecture](okf_data_flow_matrices.md) - Formal methodology for modeling complex SIMD-compatible simulation behavior, trigger cascades, and invariants using Open Knowledge Format (OKF) Data-Flow Matrices.

## Recommended Reading Order

1. Read the [Contribution & Workflows](contribution_workflow.md) guide before submitting pull requests or modifying engine systems.
2. Review [OKF Data-Flow Matrix Architecture](okf_data_flow_matrices.md) when introducing or modifying biological behavioral cascades.
3. Consult the [Agent Ecosystem](agent_ecosystem.md) to understand role delegation, IDE routing tables, and MCP tool boundaries.
4. Track strategic milestones in the [Strategic Roadmap](roadmap.md).
