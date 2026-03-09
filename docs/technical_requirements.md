Technical Tooling and Architectural Expectations

This document outlines the strict technical requirements, software stack, and computational constraints mandated for the development of the Plant-Herbivore Interaction & Defense Simulator (PHIDS). The objective is to construct a headless, highly performant, deterministic simulation engine utilizing a data-oriented Entity-Component-System (ECS) and Cellular Automata.

1. Core Technology Stack

Development must strictly adhere to the following technological stack. The deployment of these tools is governed by specific architectural mandates:

Environment Management (uv): Mandated for accelerated, deterministic dependency resolution and environment bootstrapping.

Vectorized Data Structures (numpy): Utilized exclusively for the allocation and manipulation of all continuous spatial matrices (e.g., biotope grids, energy layers). The use of native Python multi-dimensional lists is strictly prohibited due to memory overhead.

Mathematical Operations (scipy): Specifically, scipy.signal.convolve2d is required for calculating the dispersion of continuous variables across the grid per time step.

Just-In-Time Compilation (numba): The @njit decorator must be applied to high-frequency bottleneck functions—primarily the global Flow Field pathfinding gradient generation—to circumvent the Python Global Interpreter Lock (GIL) and achieve C-level execution velocities.

API and Network Layer (fastapi, uvicorn, websockets): Required to serve the headless engine. Must provide asynchronous REST endpoints for configuration and a WebSocket connection for continuous state streaming.

Telemetry Aggregation (polars): Mandated for tick-by-tick aggregation of statistical metrics into in-memory DataFrames, optimizing read/write operations for analytical exports.

Data Validation (pydantic): Required for defining rigorous, self-documenting schemata encompassing ECS Components, Global Configuration Payloads, and REST API inputs.

Binary Serialization (msgpack or flatbuffers): Requisite for the compact serialization of the state buffer at each discrete time step to facilitate deterministic re-simulation.

Architectural Diagramming (mermaid.js): Required for the programmatic visualization of system state machines and logic triggers.

2. Development Workflow and CI/CD

To ensure the integrity, performance, and maintainability of the PHIDS engine, the development pipeline must enforce the following operational tooling:

Version Control Integration (GitHub Actions): A robust Continuous Integration/Continuous Deployment (CI/CD) pipeline is mandated. It must automatically trigger on all push and pull request events to validate builds, run the test suite, and enforce linting rules before code merges.

Local Code Hygiene (pre-commit): Developers must utilize pre-commit hooks (including configurations for trailing whitespace and end-of-file fixers) to ensure no malformed code is committed to the repository.

Quality Assurance and Linting (ruff, mypy): Strict static type-checking must be enforced via mypy. All code must be linted and formatted utilizing ruff, fully integrated into both the pre-commit hooks and the CI/CD pipeline.

Automated Testing (pytest, pytest-cov, pytest-benchmark): The project mandates comprehensive testing methodologies. pytest-cov is required to enforce strict code coverage minimums. Crucially, pytest-benchmark must be employed to continuously profile the numba JIT performance and spatial hashing execution times, ensuring no algorithmic regressions occur.

Documentation Generation (mkdocs): The project mandates the use of mkdocs, utilizing the mkdocs-material theme and mkdocstrings. All Python classes, systems, and mathematical formulas must possess comprehensive docstrings that are automatically parsed and rendered into a static documentation site.

3. Architectural and Execution Constraints

3.1 State Management (Double-Buffering)

To preclude race conditions and guarantee mathematical determinism during synchronous time steps ($\Delta t$), the system must implement strict double-buffering. The simulation controller must maintain isolated State_Read and State_Write buffers. Logic systems are restricted to querying data exclusively from the read buffer and mutating data exclusively within the write buffer, executing a buffer swap strictly at the conclusion of the time step.

3.2 Memory Allocation Constraints (The "Rule of 16")

Dynamic array resizing during the simulation loop is computationally prohibitive. The architecture dictates a hard configuration limit: a maximum of 16 distinct entity classifications per type (16 flora species, 16 predator species, 16 substance types). The engine must pre-allocate all primary interaction matrices (e.g., shape (16, 16) for the Diet Compatibility Matrix and Trigger Matrix) based on these bounds during system initialization.

3.3 ECS Garbage Collection

To maintain optimal memory utilization, the ECS framework must enforce continuous garbage collection. Entities whose tracked parameters violate operational thresholds (e.g., population $n \le 0$) must be programmatically despawned, their localized memory freed, and their references purged from the Spatial Hash.

4. Computational Optimization Directives

4.1 Spatial Query Resolution ($O(1)$ Complexity)

The architectural framework must preclude inefficient $O(N^2)$ Euclidean distance evaluations for localized entity interactions. The ECS must implement a Spatial Hash or Grid Cell Roster, ensuring that positional queries (e.g., overlapping coordinate checks) are resolved with $O(1)$ temporal complexity.

4.2 Floating-Point Subnormal Mitigation

Continuous diffusion equations calculated via scipy convolutions naturally yield infinitely long tails of minuscule floating-point numbers. Processing these "subnormal" floats critically degrades CPU performance. Implementations must systematically enforce a minimum concentration threshold (e.g., truncating matrix values < 1e-4 to 0.0) immediately following convolution operations to preserve matrix sparsity.

4.3 Unified Pathfinding Gradients

Individual agent-based pathfinding calculations (e.g., Breadth-First Search) are strictly prohibited. The system must compute a singular, global flow_field_gradient per time step using numba. All discrete spatial entities must derive their vector transformations exclusively from this unified gradient.

5. Interface and Telemetry Specifications

5.1 Network Endpoints

The FastAPI interface must explicitly expose the following operational routes:

POST /api/scenario/load: Ingests a pydantic-validated JSON payload containing the biotope configuration, topological bounds, and interaction matrices.

POST /api/simulation/start and POST /api/simulation/pause: Controls the asynchronous execution loop.

WS /ws/simulation/stream: Establishes a WebSocket connection to stream compressed two-dimensional state matrices to a connected client at a fixed tick rate.

5.2 Data Export

The polars telemetry engine must provide programmatic utilities to dump aggregated Lotka-Volterra metrics (population trajectories and energy distributions) into standardized CSV or JSON formats upon simulation termination.