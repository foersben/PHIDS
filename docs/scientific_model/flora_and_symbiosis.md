---
type: scientific_model
title: "Flora Lifecycle and Symbiotic Networks"
status: active
version: 0.1
description: "Documentation for Flora Lifecycle and Symbiotic Networks in the PHIDS framework."
---

# Flora Lifecycle and Symbiotic Networks

Flora within PHIDS are stationary entities on the grid that produce the resources driving the herbivore ecosystem. While stationary, their behavior governs resource distribution, secondary defenses, and spatial networks.

## 1. Plant Reproduction & Constraints

Flora grow linearly by a species-specific rate ($g_j$), capped at $E_{max, j}$. When surplus energy is achieved, they attempt to reproduce.

### The Seed Cost

Before spawning offspring, the parent plant calculates the cost of the seed ($E_{seed}$).

**Biological Rationale:**
A plant cannot self-starve to drop a single seed. The plant's energy minus the seed cost must be greater than its survival threshold. If a seed successfully spawns, the energy is deducted.

### Dispensation & Germination

If the parent survives the check, it attempts to disperse the seed into an adjacent coordinate $(x,y)$.

**Algorithm & Germination Restrictions:**

1. **Calm Air ($Wind \approx 0$):** A bounded annulus is generated around the parent, defined by $r_{min}$ and $r_{max}$. A random polar angle $\theta$ is chosen. The seed falls at $(x + r \cos \theta, y + r \sin \theta)$.
2. **Wind-Active Air:** If wind is present, the model switches to an anemochorous kernel. It samples a Gaussian distribution aligned to the continuous wind vector $(Wind_X, Wind_Y)$, scaled by the seed's terminal velocity and drop height.
3. **The Exclusion Zone:** Seeds *cannot* germinate if they land on an already occupied grid cell. If the target coordinate is occupied, the reproductive energy is spent, but no new entity is generated.

**Biological Rationale:**
The model prevents infinite stacking. A single grid patch only has sunlight and soil capacity for one active plant organism.

## 2. Mycorrhizal Connections (The Root Network)

Plants placed at a Manhattan distance of 1 (directly adjacent orthogonally) can form a symbiotic, underground network called **Mycorrhiza**.

### Connection Economics

Establishing a new root link is a costly energetic investment for both the parent and the neighbor.

**Algorithmic Resolution:**
During the *Lifecycle Phase*, the engine filters all plants, shuffling their iteration order deterministically.

If `mycorrhizal_growth_interval_ticks` has elapsed (e.g., 8 ticks), the plant scans its 4 cardinal neighbors. If a neighbor is found, and both have sufficient energy to pay the `connection_cost` without dropping below their survival threshold, they connect.

**Biological Rationale:**
Establishing a fungal web requires significant carbohydrate expenditure. Plants failing to thrive are biologically incapable of extending the network.

### Why Are They Used?

Mycorrhizal networks bypass the airborne Volatile Organic Compound (VOC) diffusion model.

1. If Plant A is attacked, it triggers a signaling substance (Section 5.1, Reaction-Diffusion).
2. Plant A begins emitting VOCs into the air above it.
3. Simultaneously, Plant A injects the exact same signal concentration *directly* into the connected root node of Plant B.

Because the signal travels over the Graph Structure of the Mycorrhiza at $t_{velocity}$ (hops per tick), it propagates significantly faster than atmospheric diffusion.

Plant B receives the chemical warning of herbivory without having to wait for the Gaussian convolution kernel to disperse the signal through the air, allowing Plant B to synthesize its own localized Toxins preemptively.

## 3. Death & Telemetry Causation

In older OOP simulations, death is a simple variable boolean `True/False`. In PHIDS, biological extinction provides explicit causal telemetry.

Whenever a plant energy value falls beneath its survival threshold, it is scheduled for garbage collection by the ECS framework. Crucially, the engine tags exactly *why* the energy plummeted via the `last_energy_loss_cause` tracker:

- **`death_reproduction`**: The plant over-extended dropping seeds.
- **`death_mycorrhiza`**: The plant died trying to pay the cost of connecting to a fungal network.
- **`death_defense_maintenance`**: The plant successfully synthesized a defensive toxin but lacked the caloric intake to maintain it.
- **`death_herbivore_feeding`**: The plant was completely stripped of energy by a grazing swarm.
- **`death_background_deficit`**: General starvation due to low growth or high thresholds.

These tags are essential for interpreting whether an ecosystem collapsed due to herbivory or metabolic mismanagement.


## The Defense Economy: Constitutive vs. Induced Defenses

The PHIDS engine models the evolutionary resource allocation trade-offs plants make to survive grazing pressure. Defenses are categorized into two primary economic strategies:

*   **Induced Defenses (Active Chemical Traits):** These are on-demand biological weapons like Volatile Organic Compounds (VOCs) and lethal Toxins. They are highly effective but metabolically expensive. In the ECS, these are represented as dynamically spawned `SubstanceComponent` entities. They require a synthesis lead time and impose a continuous maintenance penalty (`energy_cost_per_tick`) on the host plant's energy reserve while active.
*   **Constitutive Defenses (Morphological Traits):** Governed by the `PassiveDefensesSchema`, these are permanent structural or chemical barriers integrated into the plant's tissue (e.g., lignin, silica, thorns). Because they are "always on," they require an evolutionary upfront cost (typically represented by a lower baseline `growth_rate` in the species configuration), but they impose **zero dynamic maintenance costs** during the runtime simulation loop.

## Morphological Defense Barriers

Constitutive defenses directly modify the trophic interaction loop without requiring spatial chemical diffusion.

### Mechanical Trauma (Thorns, Spines, Prickles, and Trichomes)
Configured via the `mechanical_damage_per_bite` parameter. Rather than acting as a binary edibility gate (which is handled by the `DietCompatibilityMatrix`), mechanical defenses inflict direct physical trauma on grazing swarms. When an herbivore swarm feeds on the plant, it takes immediate population reductions (casualties) proportional to the energy consumed and the severity of the plant's armament.

### Quantitative Digestibility Reductions (Lignin, Silica, and Tannins)
Configured via the `digestibility_modifier` parameter (ranging from 0.0 to 1.0). Anti-nutritional compounds structurally inhibit digestive enzymes or act as abrasive fillers. During the feeding interaction phase, the actual energy $\\Delta e$ removed from the plant is scaled down before it is added to the swarm's reproductive surplus budget:

$$
\Delta e_{\text{metabolized}} = \Delta e_{\text{consumed}} \cdot \text{digestibility\_modifier}
$$

A `digestibility_modifier` of $0.5$ forces an herbivore swarm to consume twice as much total biomass just to cover its baseline metabolic upkeep (`energy_upkeep_per_individual`), rapidly accelerating starvation kinetics despite heavy grazing activity.

## The Defense Economy: Constitutive vs. Induced Defenses

In ecological systems, plants must balance their energy budgets between growth and defense. The engine models the evolutionary resource allocation trade-offs plants make to survive grazing pressure. Defenses are categorized into two primary economic strategies:

* **Induced Defenses (Active Chemical Traits):** These are on-demand biological weapons like Volatile Organic Compounds (VOCs) and lethal Toxins. They are highly effective but metabolically expensive. In the ECS, these are represented as dynamically spawned entities. They require a synthesis lead time and impose a continuous maintenance penalty (`energy_cost_per_tick`) on the host plant's energy reserve while active.
* **Constitutive Defenses (Passive Traits):** Governed by the `PassiveDefensesSchema`, these are structural, morphological barriers permanently integrated into the leaf or stem tissue. Explain that while they require an upfront evolutionary trade-off (reducing the plant's continuous `growth_rate`), they impose zero dynamic maintenance costs at runtime.

## Morphological Defense Barriers

Constitutive defenses directly modify the trophic interaction loop without requiring spatial chemical diffusion.

### Mechanical Trauma (Thorns, Spines, Prickles, and Trichomes)

This parameter models structural plant defenses like thorns, spines, prickles, and trichomes (microscopic, needle-like hairs).

!!! info "Biological Context"
    Unlike active toxins that cause systemic internal poisoning, mechanical defenses inflict immediate, localized physical trauma to the herbivore's mouthparts, digestive tract, or soft tissues during the act of feeding.

Configured via the `mechanical_damage_per_bite` parameter. Rather than acting as a binary edibility gate (which is handled by the `DietCompatibilityMatrix`), mechanical defenses inflict direct physical trauma on grazing swarms. When an herbivore swarm feeds on the plant, it takes immediate population reductions (casualties) proportional to the energy consumed and the severity of the plant's armament.

### Quantitative Digestibility Reductions (Lignin, Silica, and Tannins)

This parameter simulates Quantitative Defenses—compounds that do not directly harm the herbivore but make the plant biologically useless as a food source.

!!! info "Biological Context"
    Plants load their mature leaves with lignin, silica, or high concentrations of tannins. Lignin and silica make the cellular structure incredibly tough and difficult to break down. Tannins actively bind to the herbivore's digestive enzymes, preventing them from extracting proteins from the consumed plant matter.

Configured via the `digestibility_modifier` parameter (ranging from 0.0 to 1.0). Anti-nutritional compounds structurally inhibit digestive enzymes or act as abrasive fillers. During the feeding interaction phase, the actual energy $\\Delta e$ removed from the plant is scaled down before it is added to the swarm's reproductive surplus budget:

$$
\Delta e_{real} = \Delta e \cdot \text{digestibility\_modifier}
$$

!!! note "Engine Constraint"
    A `digestibility_modifier` of 0.5 means that for every 10 units of $E_{max}$ the swarm bites off the plant, it only successfully metabolizes 5 units into its own surplus energy. The rest passes through as waste. This biologically forces the swarm to consume twice as much to meet its `metabolism_upkeep`, effectively starving highly active herbivores even while they are "eating."
