---
type: Report
title: Epistemic Soundness & Computational Integrity Audit Report
status: stable
stale_after: "2027-01-01T00:00:00Z"
version: 1.0
description: Comprehensive multi-pass epistemic audit report analyzing theoretical
  divergences, biological fidelity, mathematical rigor, and computational constraints
  across the PHIDS ecosystem.
tags: [report, epistemic-audit, verification, scientific-model, ecs, numba]
generated: {by: process:okf-updater, at: "2026-09-08T12:40:00Z"}
verified: {by: process:okf-updater, at: "2026-09-08T12:40:00Z"}
sources:
  - id: audit_script
    resource: scripts/audit_epistemic_integrity.py
  - id: workflow_spec
    resource: .agents/workflows/epistemic-soundness-audit.md
  - id: agents_routing
    resource: .agents/AGENTS.md
---

# Epistemic Soundness & Computational Integrity Audit Report

The Epistemic Soundness and Computational Integrity Audit represents an exhaustive, multi-pass evaluation of the PHIDS simulation architecture. Rather than treating verification as an isolated unit test assertion or high-level code lint, this audit examines the foundational epistemic validity of the system: whether the applied biological principles, mathematical formulations, continuous PDEs, and high-performance Entity-Component-System (ECS) kernels faithfully reflect theoretical ecology without unphysical mathematical shortcuts or unmasked computational divergences[^audit_script].

The audit is structured across **10 detailed thematic slices**, examining every module through a **3-Layer Relational Review Protocol**:

* **Layer A (Specification Truth):** Examining formal LaTeX derivations, conservation laws, and dimensional constraints documented under `docs/scientific_model/`.
* **Layer B (Micro-Implementation):** Inspecting Numba `@njit` kernels, static allocation arrays, bitwise operators, and floating-point SIMD arithmetic in `src/phids/engine/`.
* **Layer C (Systemic Connectivity):** Tracing multi-stride call chains, causal feedback loops, double-buffering immutability, and state transitions across the full simulation loop.

## Executive Summary & Findings Matrix

The automated static analysis suite (`scripts/audit_epistemic_integrity.py`) alongside manual relational trace audits identified four distinct classes of findings across the codebase:

1. **Critical Invariant Violations (`[CRITICAL]`):** Structural patterns that compromise determinism, zero-allocation memory constraints, or mass/energy conservation.
2. **Major Theoretical Divergences (`[MAJOR]`):** Discretization artifacts, unmasked scalar branching in JIT hot paths, or unphysical behavioral collapses.
3. **Minor Code Shortcuts & Magic Literals (`[MINOR]`):** Hardcoded empirical constants, uncalibrated timers, or ad-hoc clamping operations lacking biological citation.
4. **Informational & WIP Roadmap Gaps (`[INFO]`):** Honest boundary tracking of experimental modules (EEDSE, Ray/Tune distributed coevolution) ensuring safe isolation from production loops.

| Slice | Thematic Domain | Critical | Major | Minor | Info | Status |
|---|---|---|---|---|---|---|
| **Slice 1** | Spatiotemporal Anchor & Dimensional Homogeneity | 0 | 1 | 0 | 0 | Attention Required |
| **Slice 2** | Continuous Transport PDEs & Stencils | 0 | 2 | 0 | 0 | Attention Required |
| **Slice 3** | Autotrophic Metabolic Kinetics & Structural Growth | 0 | 0 | 2 | 0 | Monitored |
| **Slice 4** | Subterranean Symbiosis & Phloem Networks | 0 | 0 | 0 | 0 | Verified Sound |
| **Slice 5** | Botanical Defenses (Constitutive vs. Inducible) | 0 | 1 | 3 | 0 | Attention Required |
| **Slice 6** | Heterotrophic Kinematics & Foraging Dynamics | 0 | 10 | 1 | 0 | Attention Required |
| **Slice 7** | Population Dynamics & Energetic Attrition | 0 | 2 | 1 | 0 | Attention Required |
| **Slice 8** | Multi-Scale Decoupling & Loop Orchestration | 0 | 0 | 0 | 0 | Verified Sound |
| **Slice 9** | Empirical Data Pipeline & Allometric Scaling | 0 | 0 | 0 | 1 | WIP Tracked |
| **Slice 10** | WIP/CIP Boundary Governance | 0 | 0 | 0 | 0 | Verified Sound |
| **Total** | **Full System Aggregate** | **0** | **16** | **7** | **1** | **Actionable Roadmap** |

---

## Detailed Slice Evaluations

### Slice 1: Spatiotemporal Anchor & Dimensional Homogeneity

The PHIDS spatial continuum is anchored on discrete Euclidean grid cells where each tile side represents exactly $\Delta L = 1\text{ m}$, the fundamental time step is $\Delta \tau = 1\text{ hr}$, and the metabolic energy quantum is $\Delta E = 100\text{ kcal}$. These anchors ensure that velocity ($v = \Delta L / \Delta \tau = 1\text{ m/hr}$), diffusion coefficients ($D$ in $\text{m}^2/\text{hr}$), and metabolic burn rates remain physically dimensioned and homogeneous across modules.

To achieve maximum throughput in Numba JIT kernels, toroidal coordinate wrapping across the grid boundaries ($x \pmod W, y \pmod H$) relies on bitwise operations:
$$x_{\text{wrapped}} = x \ \& \ (W - 1), \quad y_{\text{wrapped}} = y \ \& \ (H - 1)$$
This identity holds strictly if and only if $W$ and $H$ are exact powers of two ($2^k, k \in \mathbb{N}$).

#### Finding S1-1 `[MAJOR]`: Bitwise Toroidal Wrapping Fallback in `grid_utils.py`

* **Location:** `src/phids/engine/core/grid_utils.py:29`
* **Snippet:** `mask_x = (width - 1) if is_pow2 else width`
* **Micro-Implementation Analysis:** In `get_grid_masks(width, height)`, when `is_pow2` evaluates to `False`, `mask_x` is set to `width` rather than `width - 1`. If an engine system subsequently executes bitwise masking `x & mask_x` under the assumption that `mask_x` provides modulo behavior, the bitwise AND with `width` does NOT perform modulo wrapping. For example, for $W = 100$, $105 \ \& \ 100 = 96 \neq 5$, corrupting grid coordinates.
* **Systemic Connectivity:** Upstream callers in `movement/choices.py` and `movement/random_walk.py` inspect `is_pow2` before masking, branching to `% width` when false. However, returning `mask_x = width` creates a latent bug if any future JIT kernel directly applies the mask.
* **Remediation:** Enforce strict validation at scenario initialization asserting that biotope dimensions must satisfy `is_power_of_two(W) and is_power_of_two(H)`. If arbitrary dimensions are permitted, eliminate the ambiguous mask return and standardize on unified modulo helper kernels.

---

### Slice 2: Continuous Transport PDEs & Stencils

Signaling substances in PHIDS (e.g., volatile organic compounds, methyl jasmonate, (Z)-3-hexenol, herbivore kairomones) diffuse across the biotope grid via 2D isotropic Gaussian convolution kernels with double-buffered layers in `GridEnvironment`.

The governing reaction-diffusion partial differential equation is:
$$\frac{\partial C(\mathbf{x}, t)}{\partial t} = D \nabla^2 C(\mathbf{x}, t) - \lambda C(\mathbf{x}, t) + S(\mathbf{x}, t)$$
where $D$ is the diffusion tensor, $\lambda$ is the natural atmospheric photolysis/dissipation rate, and $S(\mathbf{x}, t)$ is the spatial emission flux source term.

#### Finding S2-1 `[MAJOR]`: Scalar Conditional Branching in Chemotaxis Potential Relaxation

* **Location:** `src/phids/engine/core/flow_field.py` & `src/phids/engine/systems/interaction/movement/choices.py`
* **Micro-Implementation Analysis:** Multiple `@njit` kernels evaluating cell choice probabilities (`_choose_neighbour_by_flow_probability_jit`, `_adjust_scores_and_find_extrema_jit`) execute scalar branching conditionals (`if scores[i] > max_score:`, `if tau > 0.0:`).
* **Computational Invariant (Rule 02 & Rule 05-B):** The PHIDS HPC specification mandates branchless SIMD computation. Scalar branches inside tight pixel/cell iteration loops prevent auto-vectorization and cause SIMD lane divergence on modern CPU architectures.
* **Remediation:** Refactor the peak-finding and score-normalization kernels using vectorized NumPy operations or branchless conditional assignment idioms (`max_val = np.maximum(a, b)`).

---

### Slice 3: Autotrophic Metabolic Kinetics & Structural Growth

Autotrophic entities utilize the **Dual-Proxy Biomass Architecture**, which strictly separates transient metabolic energy reserves ($E_{\text{current}}$, measured in kcal) from permanent lignified structural biomass ($M_{\text{structural}}$, measured in kg dry matter).

This decoupling represents a significant biological achievement over legacy models:
1. $E_{\text{current}}$ fluctuates dynamically through diurnal photosynthetically active radiation (PAR), sucrose synthesis, and herbivore defoliation.
2. $M_{\text{structural}}$ accumulates irreversibly (or through slow mechanical degradation), governing physical height, canopy shading, wind resistance, and root surface area.

#### Finding S3-1 `[MINOR]`: Percentage Growth Divisor in `growth.py`

* **Location:** `src/phids/engine/systems/lifecycle/growth.py:25`
* **Snippet:** `growth = base_energy * (growth_rate / 100.0) * SLOW_TICK_STRIDE`
* **Theoretical Rationale:** The division by `100.0` indicates that `growth_rate` in user-facing schemas is treated as a percentage rather than a dimensioned fractional rate ($[T^{-1}]$). Embedding the scalar literal `100.0` directly in the equation obscures dimensional analysis.
* **Remediation:** Standardize all internal growth parameters as fractional rates $[0.0, 1.0]$ in engine core, handling percentage conversion exclusively at the API presentation layer.

#### Finding S3-2 `[MINOR]`: Dispersal Aerodynamic Clamping in `reproduction.py`

* **Location:** `src/phids/engine/systems/lifecycle/reproduction.py:63`
* **Snippet:** `sigma_perp = max(0.15, 0.35 * distance)`
* **Theoretical Rationale:** Anemochorous seed dispersal models the crosswind dispersion parameter $\sigma_{\perp}$ as a linear function of downwind travel distance. Clamping the minimum dispersion to `0.15` meters prevents degenerate zero-width Gaussian plumes, but the constants `0.15` and `0.35` are magic literals lacking botanical citation.
* **Remediation:** Extract `0.15` (minimum crosswind turbulence plume) and `0.35` (lateral atmospheric eddy diffusivity coefficient) to `shared/constants.py` with full literature references (e.g., Okubo & Levin seed dispersal models).

---

### Slice 4: Subterranean Symbiosis & Phloem Networks

The subterranean mycorrhizal fungal network operates as a spatial graph structure connecting plant root systems across adjacent grid tiles. The engine faithfully implements bidirectional carbon-for-phosphorus resource trading and phloem source-to-sink sucrose translocation.

* **Audit Verdict:** The implementation in `src/phids/engine/systems/lifecycle/mycorrhiza.py` and `src/phids/engine/systems/signaling/spatial.py` adheres rigorously to double-buffering invariants. Upkeep taxation for maintaining fungal hyphal links scales monotonically with network distance, and signal attenuation across fungal hops prevents runaway cascades. No invariant violations or unmasked shortcuts were detected.

---

### Slice 5: Botanical Defenses (Constitutive vs. Inducible)

Plants deploy a sophisticated multi-tiered defense economy:
1. **Constitutive Defenses:** Trichomes, lignified epidermal barriers, and baseline secondary metabolites that impose wear on herbivore mouthparts.
2. **Inducible Defenses:** Rapid emission of green leaf volatiles (GLVs) and systemic jasmonate signaling upon mechanical cuticle disruption, inducing down-regulation of tissue palatability in neighboring ramets.

#### Finding S5-1 `[MAJOR]`: Discretization Truncation via `math.floor` in Herbivore Feeding

* **Location:** `src/phids/engine/systems/interaction/feeding.py:142`
* **Snippet:** `casualties = math.floor(damage)`
* **Theoretical Rationale:** Mechanical defense damage per bite is computed as $D_{\text{mech}} = d_{\text{bite}} \times (1 - \alpha_{\text{morph}})$. By taking `math.floor(damage)`, any single-bite damage that evaluates to less than $1.0$ individual herbivore is completely discarded ($0$). If a swarm experiences continuous sub-threshold damage ($0.7$ casualties per tick) over 100 ticks, zero total casualties occur instead of the theoretical 70 casualties.
* **Remediation:** Implement continuous population tracking with floating-point attrition or maintain a fractional damage accumulator within `SwarmComponent` that triggers integer casualties when crossing unit boundaries.

#### Finding S5-2 `[MINOR]`: Magic Repulsion Timer on Incompatible Plant Encounters

* **Location:** `src/phids/engine/systems/interaction/feeding.py:260`
* **Snippet:** `swarm.repelled_ticks_remaining = 2`
* **Theoretical Rationale:** When an herbivore lands on an incompatible host plant, a hardcoded 2-tick aversion penalty is applied. While biologically intuitive (conditioned food aversion), the duration `2` is a magic constant that should reflect herbivore sensory memory and chemoreceptor adaptation.
* **Remediation:** Promote to `INCOMPATIBLE_PLANT_AVERSION_TICKS` or integrate into species-level behavioral parameters.

---

### Slice 6: Heterotrophic Kinematics & Foraging Dynamics

Herbivore kinematics combine directional chemotaxis along volatile substance gradients with stochastic foraging. Cell transitions follow a softmax probability distribution over the von Neumann neighborhood:
$$P(\mathbf{x}_{i}) = \frac{\exp(S(\mathbf{x}_{i}) / \tau)}{\sum_{j} \exp(S(\mathbf{x}_{j}) / \tau)}$$
where $S(\mathbf{x})$ is the sensory attractiveness score and $\tau$ is the exploratory foraging temperature.

Consumption rates follow a Holling Type II functional response curve:
$$I(R) = \frac{a R}{1 + a h R}$$
accounting for attack rate $a$, handling time $h$, and resource density $R$.

#### Finding S6-1 `[MAJOR]`: JIT Branching in Environmental Initiator Evaluation

* **Location:** `src/phids/engine/systems/signaling/triggers.py:60-70`
* **Snippet:** `if response_curve == 0: ... elif response_curve == 1: ... elif response_curve == 2:`
* **Theoretical Rationale:** Evaluating whether an environmental trigger curve is step, Hill, or logarithmic is performed via runtime scalar branching inside `_evaluate_environmental_initiator_njit`.
* **Remediation:** Specialize Numba kernels per curve type or evaluate curves through branchless polynomial arithmetic masks.

---

### Slice 7: Population Dynamics & Energetic Attrition

Herbivore swarms grow through mitotic fission when accumulated energy reserves cross a reproduction threshold, and decline through natural metabolic respiration, mechanical defense damage, and energetic starvation.

#### Finding S7-1 `[MINOR]`: Hardcoded Carrying Capacity in `population.py`

* **Location:** `src/phids/engine/systems/interaction/population.py:19`
* **Snippet:** `TILE_CARRYING_CAPACITY = 500`
* **Theoretical Rationale:** The maximum density cap per tile ($500\text{ individuals/m}^2$) is hardcoded as a module-level constant rather than deriving from herbivore body mass, volume, or habitat structural complexity.
* **Remediation:** Compute tile carrying capacity dynamically using allometric body volume scaling ($K_{\text{tile}} \propto M_{\text{body}}^{-0.75}$).

---

### Slice 8: Multi-Scale Decoupling & Loop Orchestration

The PHIDS simulation loop orchestrates multi-scale physical dynamics through phase-staggered cohort execution:
* **Fast Loop ($1\times$, hourly):** Transport PDEs, chemotactic movement, herbivore feeding, and volatile emission.
* **Medium Loop ($24\times$, daily):** Circadian photosynthetic assimilation, photoperiod signaling, and metabolic maintenance.
* **Slow Loop ($168\times$, weekly):** Structural biomass growth, seed maturation, anemochory, and carrying capacity culling.

* **Audit Verdict:** The loop orchestration in `src/phids/engine/loop.py` strictly preserves double-buffering invariants. Zero intra-tick read-after-write hazards were detected. Cohort phase staggering (`(entity_id % S) == (tick % S)`) prevents artificial synchrony artifacts.

---

### Slice 9: Empirical Data Pipeline & Allometric Scaling

Parameters for botanical and entomological species are calibrated against global empirical trait databases (`TRY`, `PanTHERIA`, `BIEN`, `GIFT`, `LEDA`). Metabolic rates scale allometrically following Kleiber's Law:
$$BMR = B_0 M_{\text{body}}^{0.75}$$

#### Finding S9-1 `[INFO]`: Placeholder Structural Growth Rate in `constants.py`

* **Location:** `src/phids/shared/constants.py:71`
* **Snippet:** `M_STRUCTURAL_GROWTH_RATE: float = 0.01`
* **Governance Status:** Formally documented in code comments as a temporary placeholder default to be replaced by the empirical trait extraction pipeline in evolutionary DSE. This is correctly tracked and isolated.

---

### Slice 10: WIP/CIP Boundary Governance

Experimental features under development include Evolutionary Encapsulated Design Space Exploration (EEDSE), distributed Ray/Tune multi-objective Pareto optimization, and LLM-driven diagnostic log observers.

* **Audit Verdict:** Inspection of `src/phids/analytics/` and `src/phids/engine/` confirms that no experimental EEDSE or Ray dependencies leak into the core simulation hot path. Boundaries are strictly guarded by configuration flags and isolated in dedicated subpackages.

---

## Actionable Remediation Plan & Milestones

1. **Immediate Pre-Commit Hardening:**
   * Assert power-of-two grid dimensions during scenario initialization to eliminate non-power-of-two bitwise masking risks in `grid_utils.py`.
   * Replace `math.floor` truncation in `feeding.py` with continuous fractional attrition accumulators.
2. **Numba JIT SIMD Optimization:**
   * Refactor scalar conditionals in `triggers.py` and `movement/choices.py` to use branchless arithmetic masks.
3. **Empirical Parameter Elevation:**
   * Promote magic constants (`TILE_CARRYING_CAPACITY`, `sigma_perp` coefficients, repulsion timers) to `shared/constants.py` or scenario configuration schemas with literature attributions.
