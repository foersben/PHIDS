---
type: scientific_model
title: Population Dynamics vs. Continuous Solvers
status: active
version: 0.1
description: Documentation for Population Dynamics vs. Continuous Solvers in the PHIDS
  framework.
tags:
- phids
- ecs
- python
timestamp: '2026-07-21T16:01:38Z'
resources: []
---

Herbivore swarms within PHIDS consume resources, metabolize energy, reproduce, and undergo density-dependent population scaling. This deep dive explains how those behaviors are modeled as discrete events evaluated locally on the spatial hash.

## Biological Context

Organisms require a baseline caloric intake (maintenance metabolism) to survive and fuel reproductive output (surplus metabolism). Rather than treating "starvation" as a binary switch that kills an entire swarm after $k$ ticks without food, biological decline is smooth. A population shrinks proportionately as available calories fall short of total maintenance demands.

When a population discovers abundant resources, it metabolizes the surplus energy into offspring. If the localized population density exceeds biological capacity limits, the group fractures and disperses (mitosis).

## The Mathematical Model

Instead of modeling the populations of foxes and rabbits continuously via Ordinary Differential Equations (ODEs) across an entire ecosystem, PHIDS evaluates every localized swarm $i$ at position $(x, y)$ independently during tick $t$.

### 1. Metabolic Attrition

Swarms continuously deplete their stored energy ($E_i$) proportional to their population size ($N_i$).

Let $m_i$ be the species-specific metabolic upkeep rate per individual per tick.

$$
\text{Total Upkeep} = N_i \cdot m_i
$$

If $E_i < \text{Total Upkeep}$, the swarm suffers an **Energy Deficit**. Deficits manifest as immediate casualties.

#### I. Implementation Mechanics

When a herbivore swarm suffers from an energy deficit (due to metabolic maintenance costs outstripping resource ingestion on a barren tile), the engine converts this floating-point energy deficit into discrete organism deaths.

The core calculation uses an aggressive ceiling function approach. The base death count is calculated via floor division: `int(deficit // swarm.energy_min)`. Immediately following this, the engine applies a protective rounding check:

```python
# Absolute clearing of energy debt
casualties = int(deficit // swarm.energy_min)
if casualties * swarm.energy_min < deficit:
    casualties += 1  # Ceil operation forced
```

If any fractional deficit remains un-cleared by the base floor division, the engine intentionally increments the casualties by one, sacrificing an extra individual to completely wipe out the debt.

#### II. Why It Is Solved This Way

If the engine used standard rounding or pure floor division, fractional energy deficits would be carried over across ticks as floating-point state variables attached to the swarm. Over long execution spans, tracking fractional "ghost debt" across thousands of swarms introduces precision leaks, floating-point drift, and breaks the fundamental closed-system conservation laws of the biotope.

#### III. The Historical/Continuous Alternative

Continuous models treat population counts as floating-point numbers, allowing a swarm to comfortably contain $14.234$ individuals. In an entity engine, fractional individuals break system logic; an entity must have concrete, integer-valued components to interact clearly with discrete logic gates.

#### IV. Computational Improvement

* **Complexity:** Executes as a basic $O(1)$ arithmetic check.
* **State Minimization:** By guaranteeing that no fractional energy debt is carried forward to the next tick, the engine completely removes the need to track, store, or serialize sub-individual fractional states. This reduces the feature footprint of the swarm component struct, ensuring it fits cleanly into highly efficient structured arrays optimized for direct memory cache operations.

#### V. Biological Modeling Realism

* **Strict Thermodynamic Conservation:** Energy cannot be synthesized out of nothing. If an engine allows a swarm to carry debt without paying an immediate survival penalty, it is essentially allowing organisms to survive on "ghost energy" that doesn't exist in the biotope.
* **Starvation Threshold Penalties:** Enforcing an aggressive ceiling function on starvation deaths accurately models the biological vulnerability of stressed colonies. When a collective swarm faces an energetic deficit, the structural cost of maintaining cohesion means that fractional shortages trigger rapid, cascading failure among the weakest individuals. This ensures that starvation curves remain sharp, punitive, and biologically authentic.

If $N_i \le 0$, the entity is scheduled for garbage collection at the end of the phase.

### 2. Reproduction from Surplus

If the swarm secures enough energy to fulfill its baseline viability ($E_{base} = N_i \cdot E_{min,i}$), the remaining *surplus* energy is converted into new individuals.

Let $c_i$ be the reproductive cost per offspring ($E_{min,i} \cdot \rho_i$, where $\rho_i$ is a divisor).

$$
\Delta N_i = \left\lfloor \frac{\max(0, E_i - E_{base})}{c_i} \right\rfloor
$$

### 3. Mitosis

Cellular division within a macroscopic swarm occurs when the cluster population reaches $N_i \ge N_{split}$, prompting a physical bifurcation into two discrete ECS entities that share the parent's accumulated energy.

#### I. Implementation Mechanics

During the interaction and lifecycle phase, if a swarm's population count violates the maximum threshold ($N_i \ge N_{split}$), a division event is triggered. The parent swarm splits its population array into two distinct entity segments (e.g., 7 and 8 individuals for a parent of 15).

Instead of writing both daughter swarms to the exact coordinates $(x, y)$ of the parent, the engine passes the second daughter swarm through an internal stochastic displacement routine: `_random_walk_step(swarm.x, swarm.y)`. This translates the offspring's spatial coordinates to a stochastically sampled adjacent cell in the Moore or von Neumann neighborhood before appending it to the Entity Component System (ECS) world array.

#### II. Why It Is Solved This Way

In a discrete, grid-based simulation engine utilizing an ECS paradigm, placing two distinct entities with overlapping spatial keys on the same frame introduces critical system conflicts. Without immediate dispersal, the engine would have to handle infinite immediate re-coalescence loops (where the two swarms instantly merge back together on the subsequent tick if local density rules dictate) or handle division calculations multiple times on a single spatial coordinate, stalling the pipeline.

#### III. The Historical/Continuous Alternative

The naive continuous mathematical alternative assumes that a population splits perfectly in-place, occupying a single infinitesimal point in space, with separation driven over time by continuous partial differential equations (PDEs) for repulsive movement.

#### IV. Computational Improvement

* **Complexity:** Reduces a multi-step path-finding or collision-avoidance routine down to an $O(1)$ stochastic computation.
* **Array Efficiency:** By immediately assigning the daughter swarm to a vacant or adjacent cell index during the mutation pass, the engine avoids the need for an expensive post-split "entity un-stacking" pass, which would require an $O(N \log N)$ spatial sorting or an $O(N^2)$ distance cross-check of overlapping swarms. It also minimizes memory overhead by keeping the mutation local to the active entity buffer transformation loop.

#### V. Biological Modeling Realism

* **Kin Competition and Local Overgrazing:** In real-world plant-herbivore dynamics, reproducing insects or micro-pathogens do not occupy the exact same physical space as their parental colony without causing catastrophic local resource failure.
* **Dispersal Phase:** Forcing an immediate step into an adjacent cell models an *active dispersal phase*. It ensures that offspring immediately attempt to exploit neighboring vegetation resources, realistically simulating the outward expansion of a foraging front across a plant canopy or meadow.

## Numerical Example

Imagine a swarm of 10 herbivores with a baseline upkeep $m_i = 1.0$ and a reproduction cost $c_i = 5.0$.

1. **Feeding Phase:** The swarm eats a plant, bringing its total energy $E_i$ to **35.0**.
2. **Metabolism Phase:** The swarm pays its upkeep ($10 \times 1.0 = 10.0$).
3. **Surplus Calculation:** The swarm has $35.0 - 10.0 = 25.0$ surplus energy.
4. **Reproduction:** The swarm converts the surplus into $\lfloor 25.0 / 5.0 \rfloor = 5$ new offspring.
5. **Tick Conclusion:** The swarm ends the tick with a population of **15** and $0.0$ surplus energy.

If $N_{split} = 15$, the swarm will divide into two swarms of 7 and 8 individuals. One swarm retains the parent's coordinate, while the daughter swarm is stochastically displaced to an adjacent cell to begin active dispersal.

## Alternatives Considered

### Continuous-Time ODE Solvers (Lotka-Volterra)

The classic Lotka-Volterra predator-prey (here: herbivore-plant) equations ($\frac{dx}{dt} = \alpha x - \beta xy$) model the rate of change of continuous populations.

* *Why rejected:* ODEs treat populations as perfectly mixed, homogeneous continuous variables ($x = 42.5$ rabbits). They cannot capture discrete, localized spatial events, such as a specific herd of 10 herbivores navigating around a toxic plant at coordinate $(4, 12)$.
* *Our advantage:* The discrete ECS formulation provides the spatial granularity required for physical movement, local chemical triggers, and density-dependent crowding (e.g., cell capacity repulsion) while preserving mathematical determinism.
