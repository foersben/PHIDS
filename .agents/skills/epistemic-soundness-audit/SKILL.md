---
name: epistemic-soundness-audit
type: Agent Skill
title: Epistemic Soundness & Computational Integrity Audit
status: stable
stale_after: "2027-01-01T00:00:00Z"
version: 1.0
description: Multi-pass relational audit workflow verifying biological fidelity, mathematical rigor, and HPC/ECS computational constraints across documentation and runtime code.
tags: [workflow, epistemic-audit, verification, scientific-model, ecs, numba]
generated: {by: process:agent-os-refactor, at: "2026-10-30T00:00:00Z"}
verified: {by: process:agent-os-refactor, at: "2026-10-30T00:00:00Z"}
sources:
- id: audit_epistemic_integrity
  resource: scripts/audit_epistemic_integrity.py
- id: audit_report
  resource: docs/reports/epistemic_soundness_audit_report.md
---

# Epistemic Soundness & Computational Integrity Audit

## Trigger & Purpose

Run `/epistemic-soundness-audit` whenever validating scientific model fidelity, evaluating proposed architectural refactors, or preparing for major version releases. This workflow systematically searches the documentation and codebase for theoretical misunderstandings, heuristic shortcuts, unmasked branching, and specification-to-code drift.

## Core Review Philosophy

1. **Granular Slicing:** The audit evaluates the system across **10 detailed thematic slices** rather than a high-level sweep, ensuring no helper kernel or boundary condition is overlooked.
2. **Multi-Pass Relational Connectivity:** Code is evaluated not in isolation, but through its causal connections. Critical modules (e.g., `feeding.py`, `biotope.py`, `loop.py`) are evaluated multiple times across different slices from distinct domain perspectives.
3. **Honest Epistemic Boundary Governance:** Modules formally flagged with `WIP/CIP` (e.g., EEDSE, Ray/Tune distributed coevolution) are audited for boundary containment and honest documentation. Any unflagged module is held to uncompromising production-grade scientific standards.
4. **Bidirectional Spec Traceability:** Forward audit (Docs $\to$ Code) verifies implemented equations; Reverse audit (Code $\to$ Docs) identifies undocumented magic constants, ad-hoc `np.clip` operations, and heuristics.

## The 10 Detailed Thematic Audit Slices

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
  * Olfactory sensing, substance masking, and repellent deterrence vectors.
  * Handling time refractory states and incidental foraging tax.

* **Slice 7: Population Dynamics & Energetic Attrition**
  * Basal metabolic maintenance, energetic debt, and culling triggers.
  * Herbivore reproduction threshold, gestation, and juvenile provisioning.
  * Clonal mitosis and spatial crowding inhibition.

* **Slice 8: Multi-Scale Decoupling & Loop Orchestration**
  * Sub-tick diffusion vs. super-tick macro dynamics stride synchronization.
  * Temporal stride alignment ($1\text{ hr}$, $24\text{ hr}$, $168\text{ hr}$).
  * Double-buffered read/write plane causality and barrier synchronization.

* **Slice 9: Empirical Data Pipeline & Allometric Scaling**
  * Trait derivation from TRY/BIEN databases and missing value imputation.
  * Allometric scaling laws and parameter bounding.

* **Slice 10: WIP/CIP Boundary Governance**
  * Confinement of exploratory code outside production simulation loops.
  * Explicit marking of provisional heuristics.

## Execution

Execute the programmatic audit suite:
```bash
uv run python scripts/audit_epistemic_integrity.py --all --fail-on-critical
```
