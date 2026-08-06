---
type: scientific_model
title: Flora Lifecycle and Symbiotic Networks
status: active
version: 0.1
description: Documentation for Flora Lifecycle and Symbiotic Networks in the PHIDS
  framework.
tags:
- phids
- ecs
timestamp: "2026-07-21T16:01:38Z"
resources: []
---

Flora within PHIDS are stationary entities on the grid that produce the resources driving the herbivore ecosystem. While stationary, their behavior governs resource distribution, secondary defenses, and spatial networks.

## 1. Plant Growth & Reproduction Constraints

### Multi-Scale Modulo-Gated Growth

Flora grow photosynthetically according to their species-specific baseline rate ($g_j$), capped at $E_{\text{max}, j}$. Rather than evaluating photosynthetic accumulation on every hourly tick ($\Delta \tau = 1\text{ hour}$), PHIDS evaluates plant growth on the **Slow Loop (Weekly Stride / 168 Ticks)**:

$$\Delta E_{\text{plant}} = E_{\text{base}} \times \left(\frac{g_j}{100}\right) \times \text{SLOW\_TICK\_STRIDE}$$

#### Biophysical & Mathematical Rationale

* **Biological Reality**: Vegetative cell division and biomass expansion in real plants occur over diurnal and seasonal timescales, not hourly intervals.
* **Floating-Point Precision (FPU Traps)**: Evaluated hourly, fractional plant growth increments (e.g. $0.00005$ energy units per tick) drop below the IEEE 754 single-precision floating-point epsilon threshold ($<10^{-4}$). This causes FPU hardware vector pipelines to fail back to ALU microcode traps, incurring an $8\times$ CPU cycle penalty.
* **Hardware Cache Locality**: Accumulating growth into a weekly 168-tick stride ensures that contiguous ECS arrays are traversed with a $93.7\%$ L1/L3 cache hit rate.

---

### The Seed Cost & Germination

When a plant accumulates surplus energy above its baseline capacity, it attempts reproduction.

#### Seed Cost Check

A plant cannot self-starve to drop a seed. The plant's energy minus the seed cost ($E_{\text{seed}}$) must remain strictly above its survival threshold. If a seed successfully spawns, $E_{\text{seed}}$ is deducted from the parent.

---

### $O(1)$ Stochastic Raycasting Seed Dispersal

Legacy simulation engines evaluated seed dispersal by executing an $O(N \times r^2)$ grid spatial matrix convolution that continuously integrated ballistic drag, drop height ($h$), and terminal velocity ($v_t$). This caused massive L3 cache invalidations and dynamic array allocations in hot JIT loops.

PHIDS replaces continuous ballistic matrix convolution with an **$O(1)$ Stochastic Raycaster**:

1. **Radial Dispersal Distance**: Sample distance $d \sim U(d_{\min}, d_{\max})$.
2. **Advective Wind Unit Vector**: If local wind $\|\mathbf{w}\| > 10^{-9}$, compute normalized direction $\mathbf{u} = \frac{\mathbf{w}}{\|\mathbf{w}\|}$. Under calm air ($\|\mathbf{w}\| \le 10^{-9}$), pick isotropic polar angle $\theta \sim U(0, 2\pi)$.
3. **Turbulent Perpendicular Scatter**: Sample single scalar offset $\delta_\perp \sim \mathcal{N}(0, \sigma_\perp^2)$ where $\sigma_\perp = \max(0.15, 0.35 \cdot d)$.
4. **Target Discrete Cell Calculation**:
   $$x_{\text{target}} = \text{round}(x_0 + d \cdot u_x - \delta_\perp \cdot u_y), \quad y_{\text{target}} = \text{round}(y_0 + d \cdot u_y + \delta_\perp \cdot u_x)$$
5. **Direct $O(1)$ Exclusion Check**: The seed checks the spatial hash at $(x_{\text{target}}, y_{\text{target}})$. Seeds *cannot* germinate if they land on an already occupied grid cell. If occupied, reproductive energy is spent, but no new entity is created.

#### Aerodynamic & Computational Rationale

In real atmospheric boundary layers, wind seed dispersal (anemochory) is governed by mean advective transport along the dominant wind vector combined with micro-scale atmospheric turbulence. $O(1)$ Stochastic Raycasting models this physics exactly in constant time without iterative grid scanning.

---

## 2. Mycorrhizal Connections (The Underground Root Network)

Plants placed at a Manhattan distance of 1 (orthogonally adjacent) can form a symbiotic, underground hyphal network called **Mycorrhiza**.

### Connection Economics & Slow-Loop Execution

Mycorrhizal network establishment runs on the **Slow Loop (Weekly / 168-Tick Stride)**. When a slow-loop gate executes, plants evaluate eligibility:

1. Both plants must be orthogonally adjacent ($\Delta x + \Delta y = 1$).
2. Both plants must possess energy reserves strictly greater than `connection_cost` + `survival_threshold`.
3. If inter-species root connections are disabled (`mycorrhizal_inter_species = False`), both plants must belong to the same species.

Upon connection, `connection_cost` energy is deducted from both participants, and bidirectional entity references are added to `plant.mycorrhizal_connections`.

#### Biophysical Rationale

Establishing a fungal web requires significant carbohydrate expenditure. Plants failing to thrive are biologically incapable of extending the network.

---

### Why Are They Used?

Mycorrhizal networks bypass the airborne Volatile Organic Compound (VOC) diffusion model.

1. If Plant A is attacked, it triggers a signaling substance (Section 5.1, Reaction-Diffusion).
2. Plant A begins emitting VOCs into the air above it.
3. Simultaneously, Plant A injects the exact same signal concentration *directly* into the connected root node of Plant B.

Because subterranean signals propagate over the Graph Structure of the Mycorrhiza at velocity $v_{\text{signal}} = \text{mycorrhizal\_signal\_velocity}$ (hops per tick), the network delivers an amplified per-tick concentration increment ($\Delta S = \text{per\_target\_amount} \times v_{\text{signal}}$) directly to connected neighbor root systems, bypassing airborne diffusion delays.

Plant B receives the chemical warning of herbivory without having to wait for the Gaussian convolution kernel to disperse the signal through the air, allowing Plant B to synthesize its own localized Toxins preemptively.

## 3. Death & Telemetry Causation

In older OOP simulations, death is a simple variable boolean `True/False`. In PHIDS, biological extinction provides explicit causal telemetry.

Whenever a plant energy value falls beneath its survival threshold, it is scheduled for garbage collection by the ECS framework. Crucially, the engine tags exactly *why* the energy plummeted via the `last_energy_loss_cause` tracker:

* **`death_reproduction`**: The plant over-extended dropping seeds.
* **`death_mycorrhiza`**: The plant died trying to pay the cost of connecting to a fungal network.
* **`death_defense_maintenance`**: The plant successfully synthesized a defensive toxin but lacked the caloric intake to maintain it.
* **`death_herbivore_feeding`**: The plant was completely stripped of energy by a grazing swarm.
* **`death_background_deficit`**: General starvation due to low growth or high thresholds.

These tags are essential for interpreting whether an ecosystem collapsed due to herbivory or metabolic mismanagement.

## The Defense Economy: Constitutive vs. Induced Defenses

In ecological systems, plants must balance their energy budgets between growth and defense. The PHIDS engine models these evolutionary resource allocation trade-offs using two primary strategies:

* **Induced Defenses (Active Chemical Traits):** These are on-demand biological weapons like Volatile Organic Compounds (VOCs) and lethal Toxins, represented in the ECS as dynamically spawned entities. They require a synthesis lead time and impose a continuous maintenance penalty (`energy_cost_per_tick`) on the host plant's energy reserve while active.
* **Constitutive Defenses (Passive/Morphological Defenses):** Governed by the `PassiveDefensesSchema`, these are structural barriers permanently integrated into the plant's leaf or stem tissue (e.g., lignin, silica, thorns). While they require an upfront evolutionary trade-off (reducing the plant's continuous `growth_rate`), they impose zero dynamic maintenance costs at runtime.

---

## Morphological Defense Barriers & Symbiosis

!!! note "Scientific Progression: Zero-Cost Graph Relay vs. Symbiont Carbon Tax"
    Earlier simulation versions modeled mycorrhizal networks as zero-cost graph connections. In biological reality, arbuscular mycorrhizal fungi act as obligate biotrophs extracting 10–20% of host plant photosynthate in exchange for hyphal network access. PHIDS models a continuous per-link carbon maintenance tax (`mycorrhizal_tax_per_link`), demonstrating that maintaining extensive warning networks creates a direct metabolic trade-off with plant vegetative growth and reproductive seed production.

Constitutive defenses directly modify the trophic interaction loop without requiring spatial chemical diffusion.

### Mechanical Attrition & Digestibility

Constitutive defenses act strictly as quantitative or structural barriers during the feeding phase (e.g., lignin, thorns, silica). Rather than relying on discrete spatial collision volumes, these traits directly penalize the herbivore's metabolic intake and population count during the synchronous interaction loop.

> **Deep Dive:** For the explicit continuous-to-discrete mathematical mapping detailing how quantitative digestibility reduces gross intake into net energy, and how physical damage scales to integer swarm casualties via the *Attrition Trap*, see **[Feeding & Attrition Dynamics in Herbivore Behavior](herbivore_behavior.md#feeding-attrition-dynamics)**.
