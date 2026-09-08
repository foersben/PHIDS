---
type: Agent Workflow
title: Epistemic Soundness & Computational Integrity Audit
status: stable
stale_after: "2027-01-01T00:00:00Z"
version: 1.0
description: Multi-pass relational audit workflow verifying biological fidelity,
  mathematical rigor, and HPC/ECS computational constraints across documentation
  and runtime code.
tags: [workflow, epistemic-audit, verification, scientific-model, ecs, numba]
generated: {by: process:okf-updater, at: "2026-09-08T12:40:00Z"}
verified: {by: process:okf-updater, at: "2026-09-08T12:40:00Z"}
sources:
- id: audit_epistemic_integrity
  resource: scripts/audit_epistemic_integrity.py
- id: audit_report
  resource: docs/reports/epistemic_soundness_audit_report.md
---

# Trigger & Purpose

Run `/epistemic-soundness-audit` whenever validating scientific model fidelity, evaluating proposed architectural refactors, or preparing for major version releases. This workflow systematically searches the documentation and codebase for theoretical misunderstandings, heuristic shortcuts, unmasked branching, and specification-to-code drift.

# Core Review Philosophy

1. **Granular Slicing:** The audit evaluates the system across **10 detailed thematic slices** rather than a high-level sweep, ensuring no helper kernel or boundary condition is overlooked.
2. **Multi-Pass Relational Connectivity:** Code is evaluated not in isolation, but through its causal connections. Critical modules (e.g., `feeding.py`, `biotope.py`, `loop.py`) are evaluated multiple times across different slices from distinct domain perspectives.
3. **Honest Epistemic Boundary Governance:** Modules formally flagged with `WIP/CIP` (e.g., EEDSE, Ray/Tune distributed coevolution) are audited for boundary containment and honest documentation. Any unflagged module is held to uncompromising production-grade scientific standards.
4. **Bidirectional Spec Traceability:** Forward audit (Docs $\to$ Code) verifies implemented equations; Reverse audit (Code $\to$ Docs) identifies undocumented magic constants, ad-hoc `np.clip` operations, and heuristics.

# The 10 Detailed Thematic Audit Slices

* **Slice 1: Spatiotemporal Anchor & Dimensional Homogeneity**
  * Anchor constants ($\Delta L = 1\text{ m}$, $\Delta \tau = 1\text{ hr}$, $\Delta E = 100\text{ kcal}$).
  * Power-of-two bitwise toroidal coordinate wrapping (`& (width - 1)`).
  * Static array pre-allocation bounds (Rule of 16).

* **Slice 2: Continuous Transport PDEs & Stencils**
  * Double-buffered 2D isotropic Gaussian convolution kernels (`biotope.py`).
  * Semi-Lagrangian advection and mass conservation.
  * FTZ / DAZ subnormal float truncation below `SIGNAL_EPSILON` ($1\times 10^{-4}$).
  * Jacobi potential relaxation and obstacle masking (`flow_field.py`).

* **Slice 3: Autotrophic Metabolic Kinetics & Structural Growth**
  * Decoupled Dual-Proxy biomass architecture ($E_{\text{current}}$ vs. $M_{\text{structural}}$).
  * Photosynthetic daily flux and maintenance respiration.
  * Anemochorous seed dispersal aerodynamics and polar raycasting.

* **Slice 4: Subterranean Symbiosis & Phloem Networks**
  * Mycorrhizal fungal graph topology and root link maintenance taxation.
  * Phloem source-to-sink translocation kinetics.
  * Subterranean multi-hop signal propagation and hop attenuation.

* **Slice 5: Botanical Defenses (Constitutive vs. Inducible)**
  * Trichome mechanical density, spine deterrents, and structural wear.
  * Herbivore grazing damage thresholds and stress-induced apparent nutrition discounts.
  * Induced semiochemical emission cascades and olfactory camouflage.

* **Slice 6: Heterotrophic Kinematics & Foraging Dynamics**
  * Softmax stochastic gradient ascent across von Neumann orthogonal tiles.
  * Holling Type II functional consumption curves and handling times.
  * Charnov Marginal Value Theorem (MVT) patch residence and departure thresholds.

* **Slice 7: Population Dynamics & Energetic Attrition**
  * Density-dependent carrying capacity and branchless volumetric collision masking.
  * Swarm mitosis surplus energy criteria.
  * Smooth starvation attrition budgets vs. unphysical binary collapse.

* **Slice 8: Multi-Scale Decoupling & Loop Orchestration**
  * Fast ($1\times$), Medium ($24\times$), and Slow ($168\times$) loop boundaries.
  * Phase-staggered cohort execution (`(entity_id % S) == (tick % S)`).
  * Double-buffering immutability (zero intra-tick read-after-write hazards).

* **Slice 9: Empirical Data Pipeline & Allometric Scaling**
  * Trait extraction pipeline (`TRY`, `PanTHERIA`, `BIEN`, `GIFT`, `LEDA`).
  * Kleiber's Law allometric metabolic scaling ($BMR \propto M^{0.75}$).
  * Parameter reconciliation between ETL exports and engine runtime presets.

* **Slice 10: WIP/CIP Boundary Governance**
  * Evolutionary Encapsulated Design Space Exploration (EEDSE).
  * Distributed Ray/Tune Pareto optimization scaffolding.
  * Agentic diagnostic observer integration and HITL/AITL intervention gates.

# Step-by-Step Execution Protocol

1. **Static Pre-Scan (`@engine-developer` & `@matrix-auditor`):**
   * Run `uv run python scripts/audit_epistemic_integrity.py --all` to gather automated diagnostics on scalar branches in JIT, undocumented constants, and unlinked formulas.
2. **Deep Slice Evaluation (`@scientific-architect` & `@causal-verifier`):**
   * For each slice, execute the 3-Layer Relational Review:
     * *Layer A (Specification Truth):* Read target documentation equations and OKF metadata in `docs/scientific_model/`.
     * *Layer B (Micro-Implementation):* Inspect Numba `@njit` kernels and raw array math in `src/phids/engine/`.
     * *Layer C (Systemic Connectivity):* Trace upstream inputs, downstream causal effects, and feedback loops across the simulation loop.
3. **Synthesis & Report Generation (`@docs-librarian` & `@orchestrator`):**
   * Compile findings into `docs/reports/epistemic_soundness_audit_report.md`.
   * Assign severity: `[CRITICAL - INVARIANT VIOLATION]`, `[MAJOR - THEORETICAL DIVERGENCE]`, `[MINOR - CODE SHORTCUT]`, or `[INFO - WIP ROADMAP GAP]`.
   * Provide exact file links, quoted specs, quoted implementations, causal risk analysis, and concrete remediation paths.
