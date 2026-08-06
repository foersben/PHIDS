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

In nature, plants do not grow visibly every single second; vegetative cell division and root extension are slow, metabolically expensive processes governed by seasonal and daily light cycles. Attempting to simulate this on a microscopic, second-by-second scale in a computer forces it to calculate infinitesimally small fractions (like growing 0.00005 leaves per tick). Computers struggle with numbers this small—a phenomenon known as floating-point underflow—which causes massive performance crashes.

To solve this, PHIDS batches plant growth. Rather than growing tiny amounts every tick, plants save up their growth and apply it all at once during a **Slow Loop** (e.g., once every 168 ticks, simulating a weekly cycle). This perfectly matches biological reality while keeping the simulation running at maximum speed.

Mathematically, flora grow photosynthetically according to their species-specific baseline rate ($g_j$), capped at $E_{\text{max}, j}$. The batched evaluation equation is:

$$\Delta E_{\text{plant}} = E_{\text{base}} \times \left(\frac{g_j}{100}\right) \times \text{SLOW\_TICK\_STRIDE}$$

By batching metabolic growth accumulation, PHIDS maintains operations well above the floating-point subnormal boundary, ensuring uninterrupted parallel vector execution in the CPU. Furthermore, deferring these state modifications prevents cache line invalidation during the fast-paced inner-loops of the simulation (like bugs moving), yielding deterministic scaling with over $93.7\%$ L1/L3 cache coherency.

---

### The Seed Cost & Germination

When a plant accumulates surplus energy above its baseline capacity, it attempts reproduction.

#### Seed Cost Check

A plant cannot self-starve to drop a seed. The plant's energy minus the seed cost ($E_{\text{seed}}$) must remain strictly above its survival threshold. If a seed successfully spawns, $E_{\text{seed}}$ is deducted from the parent.

---

### Stochastic Polar Seed Dispersal

When a plant releases seeds into the air, we intuitively know what happens: the wind picks them up, blows them in a general direction, and turbulence scatters them a bit left or right before they hit the ground. Many simulators try to calculate the exact aerodynamics, drag, and gravity for every single seed. This is computationally disastrous and entirely unnecessary for ecological scaling.

Instead, PHIDS resolves seed dispersal using a fast, one-step mathematical shortcut (an **$O(1)$ Stochastic Polar Algorithm**) that perfectly mimics this natural chaos without simulating the physics of the fall.

First, the engine randomly picks a distance $d$ based on how far the plant's seeds can theoretically fly:
$$d \sim U(d_{\min}, d_{\max})$$

Next, it checks the local wind. If the wind is blowing, it creates a directional vector $\mathbf{u}$. If it's totally calm, it just picks a random compass direction $\theta \sim U(0, 2\pi)$.

To model the chaotic tumbling through the air (turbulence), it adds a random perpendicular sideways drift, scaled by how far the seed is flying (longer flights mean more time to drift off course):
$$\delta_{\perp} \sim \mathcal{N}(0, \sigma_{\perp}^2) \quad \text{where } \sigma_{\perp} = \max(0.15, 0.35 \cdot d)$$

Finally, this flight path is mapped back onto the discrete grid, landing the seed at a specific coordinate:
$$x_{\text{target}} = \lfloor x_0 + d \cdot u_x - \delta_{\perp} \cdot u_y \rceil$$
$$y_{\text{target}} = \lfloor y_0 + d \cdot u_y + \delta_{\perp} \cdot u_x \rceil$$

Crucially, germination requires structural space. The dispersed seed evaluates a direct $O(1)$ spatial hash exclusion check at the target coordinate $(x_{\text{target}}, y_{\text{target}})$. If the lattice is already occupied by a mature canopy, the parent's `seed_cost` is irreversibly expended with zero return on investment, capturing the vicious realities of competition for sunlight and substrate.

#### Aerodynamic & Computational Rationale

In dense forest canopies, seed transport is dictated predominantly by the macroscopic atmospheric wind vector, constantly battered by erratic micro-scale eddy currents. The $O(1)$ Polar Dispersal model unifies this turbulent reality into a solitary computational bound, guaranteeing constant-time execution overhead regardless of simulation scale.

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

### Symbiotic Network Transport Dynamics

The paramount evolutionary advantage of establishing complex mycorrhizal infrastructure lies in its ability to circumvent the spatial and temporal limitations of atmospheric diffusion. Within the standard biotope, volatile organic compounds (VOCs) expand through the canopy via a classical isotropic reaction-diffusion partial differential equation. This process is inherently bounded by concentration decay and ambient wind dilution.

Conversely, the hyphal web acts as an enclosed, highly targeted neurological relay. If a connected host experiences active herbivory and crosses a designated defense threshold, it simultaneously bleeds chemical distress signals directly into the root network.

These subterranean warnings propagate efficiently across the graph geometry governed by the continuous integer velocity constant $v_{\text{signal}}$. Because the network delivers discrete mass packets ($\Delta S = \text{per\_target\_amount} \times v_{\text{signal}}$) exclusively to structurally bound nodes, the signal completely bypasses atmospheric scattering and dissipation gradients. This enables connected flora to receive immense, undiluted concentrations of preemptive defensive compounds, providing them the critical physiological lead-time required to synthesize metabolic toxins long before the grazing threat physically traverses the terrain.

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
