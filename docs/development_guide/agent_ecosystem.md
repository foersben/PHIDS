---
type: Guide
title: Agent Ecosystem & MCP
status: stable
stale_after: "2027-01-01T00:00:00Z"
version: 1.0
description: Documentation for Agent Ecosystem & MCP in the PHIDS framework.
tags: [phids, agents, workflows, mcp]
generated: {by: process:okf-updater, at: "2026-07-21T16:01:38Z"}
verified: {by: process:okf-updater, at: "2026-09-08T12:40:00Z"}
sources:
  - id: agents_routing
    resource: .agents/AGENTS.md
  - id: epistemic_workflow
    resource: .agents/workflows/epistemic-soundness-audit.md
---

To manage documentation, testing, and lifecycle operations reproducibly, PHIDS integrates an explicit human-and-agent governance model based on the Model Context Protocol (MCP).

## Agent Roles & Governance

To keep implementation truth, documentation truth, and verification truth separated until they can be deliberately reconciled, tasks are routed to specialized agents:

* **`docs-librarian`**: The centralized coordinator for all documentation logic, structure, and validation. It maintains the Information Architecture (IA) and delegates concrete file writing.
* **`docs-scientist`**: Dedicated to writing formal, equation-backed scientific and mathematical modeling documentation (like those found in the Scientific Model deep dives).
* **`docs-operator`**: Focuses on operational, procedural guides tailored to developer execution, CI runbooks, and repository configurations.
* **`git-ops`**: The sole agent authorized to manage repository commits, branches, and PR workflows. It safeguards clean commit slices and strictly respects remote-impacting authorizations.
* **`test-ops`**: Triggers, evaluates, and resolves failures in the test suites, typing coverage, and benchmark outputs, isolating the smallest valid failing slice before pushing fixes upstream.
* **`dse-log-observer`**: Asynchronous telemetry observer performing generational DSE journaling and high-precision systemic anomaly detection. See [Agentic Diagnostic Log Writer](../scenario_guide/future_prospects/agentic_log_writer.md).

## Agent Workflows

PHIDS coordinates multi-agent operations via formal workflows defined under `.agents/workflows/`:

* **Full-Stack Validation (`/validate-full-stack`)**: Coordinates pre-commit quality gates, OKF compliance, matrix trace parity, and Zensical documentation builds.
* **Epistemic Soundness & Computational Integrity Audit (`/epistemic-soundness-audit`)**: Multi-pass relational audit workflow verifying biological fidelity, mathematical rigor, and HPC/ECS computational constraints across documentation and runtime code.
* **Matrix TDD Refactor (`/matrix-tdd-refactor`)**: Coordinated pipeline translating conceptual behavior to Data-Flow Matrix specifications, failing Pytest trace tests, branchless Numba kernels, and verified audits.
* **Matrix Drift Reconciliation (`/matrix-drift-reconciliation`)**: Automated workflow detecting, reconciling, and updating documented Data-Flow Matrices when engine parameters or telemetry drift.
* **Scientific Model Implementation (`/implement-scientific-model`)**: Process for adding ecological and mathematical behaviors with complete biological grounding.
* **Vertical Slice Development (`/vertical-slice-development`)**: Coordinated pipeline for building full-stack simulation features.
* **Delegation Protocol (`/delegation-protocol`)**: Escalation checklist for human-assisted tasks when agents encounter structural blocks.

### The 10-Slice Epistemic Audit Methodology

The `/epistemic-soundness-audit` workflow decomposes the simulation ecosystem into 10 granular thematic slices, evaluating each through a 3-layer relational review (Specification Truth -> Micro-Implementation -> Systemic Connectivity):

1. **Slice 1: Spatiotemporal Anchor & Dimensional Homogeneity:** Base scales ($\Delta L = 1\text{ m}$, $\Delta \tau = 1\text{ hr}$, $\Delta E = 100\text{ kcal}$), power-of-two bitwise toroidal coordinates, and static allocation bounds.
2. **Slice 2: Continuous Transport PDEs & Stencils:** Double-buffered 2D Gaussian convolution, semi-Lagrangian advection, FTZ/DAZ subnormal truncation, and Jacobi potential relaxation.
3. **Slice 3: Autotrophic Metabolic Kinetics & Structural Growth:** Decoupled Dual-Proxy biomass architecture ($E_{\text{current}}$ vs. $M_{\text{structural}}$), photosynthetic daily flux, maintenance respiration, and anemochorous seed dispersal.
4. **Slice 4: Subterranean Symbiosis & Phloem Networks:** Mycorrhizal fungal graph topology, root link maintenance taxation, phloem source-sink translocation, and subterranean multi-hop signaling.
5. **Slice 5: Botanical Defenses (Constitutive vs. Inducible):** Trichome density, structural wear, grazing damage thresholds, induced semiochemical emission cascades, and olfactory camouflage.
6. **Slice 6: Heterotrophic Kinematics & Foraging Dynamics:** Softmax stochastic gradient ascent across von Neumann orthogonal tiles, Holling Type II consumption curves, and Charnov MVT patch residence.
7. **Slice 7: Population Dynamics & Energetic Attrition:** Density-dependent carrying capacity, branchless volumetric collision masking, swarm mitosis surplus energy criteria, and smooth starvation attrition.
8. **Slice 8: Multi-Scale Decoupling & Loop Orchestration:** Fast ($1\times$), Medium ($24\times$), and Slow ($168\times$) loop boundaries, phase-staggered cohort execution, and double-buffering immutability.
9. **Slice 9: Empirical Data Pipeline & Allometric Scaling:** Trait extraction pipeline (`TRY`, `PanTHERIA`, `BIEN`, `GIFT`, `LEDA`), Kleiber's Law allometric scaling ($BMR \propto M^{0.75}$), and parameter reconciliation between ETL exports and engine presets.
10. **Slice 10: WIP/CIP Boundary Governance:** Evolutionary Encapsulated Design Space Exploration (EEDSE), distributed Ray/Tune Pareto optimization, and agentic diagnostic observers.

## Model Context Protocol (MCP) Capabilities

MCP defines the strict technical surface connecting the repository tooling to the AI agents. While the agent governance dictates *who* executes a task, the MCP capability layer defines exactly *what* an AI can read or execute through the connected PHIDS server.

It consists of three distinct classes:

* **Resources**: Read-only contexts providing state visibility without execution side effects. For example, `phids://config/draft.json` exposes the full active scenario draft configuration without spending a tool-call budget.
* **Tools**: Executable actions governed by safety barriers. These actively inspect the repository or the runtime environment. Available tools include `runtime_snapshot` (enhanced counts and dimensions), `inspect_telemetry_schema` (Zarr data layout visibility), `validate_okf_compliance` (pre-commit aligned constraint verification), `query_diagnostic_logs`, `validate_simulation_config` (pre-verifying AI-generated configurations), `query_telemetry_schema` (discovering export metrics), and `export_telemetry_data` (generating headless academic artifact plots like PNG, TikZ, CSV directly as string/base64 payloads for agents).
* **Prompts**: Standardized instructions utilized during specific triage operations to improve consistency (e.g., `analyze_simulation_drift` for debugging workflow bootstrapping).

Agents do not execute generic, arbitrary operations; rather, they rely on specifically registered MCP Tools assigned to their governance role to affect the repository deterministically.
