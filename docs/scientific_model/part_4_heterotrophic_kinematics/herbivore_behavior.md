---
type: Scientific Model
title: Herbivore Behavior & Kinematics
status: stable
stale_after: "2027-01-01T00:00:00Z"
version: 0.1
description: Documentation for Herbivore Behavior & Kinematics in the PHIDS
  framework.
tags: [phids, ecs, numba, chemotaxis, python]
generated: {by: process:okf-updater, at: "2026-07-21T16:01:38Z"}
verified: {by: process:okf-updater, at: "2026-08-14T16:00:00Z"}
sources:
  - id: herbivore_movement
    resource: src/phids/engine/systems/interaction/movement/__init__.py
  - id: feeding
    resource: src/phids/engine/systems/interaction/feeding.py
  - id: metabolism
    resource: src/phids/engine/systems/interaction/metabolism.py
  - id: trace_tests
    resource: tests/integration/scientific_invariants/test_causal_data_flow_matrices.py
---

Herbivore swarms represent the primary consumer tier in the PHIDS simulation. Their behaviors-movement, feeding, population scaling, and division-are carefully bounded by biological rules that produce macroscopic swarm dynamics without relying on expensive global computation.

## 1. Marginal Value Theorem (MVT) & Softmax Stochastic Foraging

In real ecological systems, individuals in a herd do not possess perfect information, nor do they perfectly converge on a single optimal point (which would create a physical singularity). Furthermore, animals do not stay on a resource patch until it is completely barren; they leave when the local intake rate drops below the expected average intake rate of the surrounding landscape. This concept is biologically known as **Charnov's Marginal Value Theorem (MVT)**.

To computationally model "diffuse foraging fronts" and MVT patch departure, PHIDS utilizes **Softmax Stochastic Action Selection** across a 4-way orthogonal **Von-Neumann Neighborhood** $\mathcal{V}(x,y)$.

Instead of greedy, deterministic gradient ascent, transition probabilities are assigned to neighboring cells using the Boltzmann distribution:

$$P(\text{move to } j) = \frac{\exp\left(\frac{F_j}{\tau}\right)}{\sum_{k \in \mathcal{V}} \exp\left(\frac{F_k}{\tau}\right)}$$

Where:

- $F_j$ is the combined chemotactic Flow Field potential of neighbor $j$.
- $\tau$ (Temperature) is a tunable parameter controlling deterministic versus stochastic behavior.

### The Biological Impact of Temperature ($\tau$)

The $\tau$ parameter directly controls the swarm's foraging paradigm:

- **Low Temperature ($\tau \to 0$):** Exploitation mode. The swarm moves almost deterministically to the cell with the highest potential. This mimics highly starved or strongly driven insects locked onto a rich pheromone trail.
- **High Temperature ($\tau > 1.0$):** Exploration mode. The swarm moves more randomly, ignoring slight variations in the gradient. This simulates exploratory grazing or movement in an environment filled with noisy, conflicting scent profiles.

By continuously evaluating the landscape via this stochastic weighting on every tick, swarms naturally exhibit density-dependent herd dispersion and realistic patch-abandonment kinetics without relying on artificial state-locking routines.

## 2. Inertial Persistence (The Orthokinetic Rule)

An animal searching a barren landscape does not spin in circles; it maintains a general heading until it intersects a new scent trail or geographic feature. This directional persistence is biologically known as *orthokinesis*.

A critical edge case occurs in the engine when the entire gradient is mathematically flat (values $< 1 \times 10^{-6}$). This implies the swarm is entirely outside the sensory horizon of any plant or toxin. If gradient ascent alone drove the system, the swarm would halt completely.

### Algorithmic Resolution

To prevent unnatural paralysis when $F_t(u,v) \approx 0$, the swarm relies on **movement inertia** stored from its previous tick (`last_dx`, `last_dy`).

- A 10:1 directional momentum preference weight ($\text{ORTHOKINETIC\_MOMENTUM\_WEIGHT} = 10.0$) is given to continue moving in the current heading.
- If no previous heading exists, isotropic random dispersal (Random Walk) is applied until a new scent gradient is found.

## 3. Capacity Limits & Physical Repulsion

The biotope is a discrete grid. While multiple swarms can occupy the same $(x, y)$ coordinate, doing so infinitely violates spatial realism.

### Algorithmic Resolution

At the start of the interaction phase, PHIDS aggregates the total population of all swarms currently on a tile. If this sum exceeds the `TILE_CARRYING_CAPACITY` (defined in `constants.py` as 500 individuals and configurable via `SimulationConfig.tile_carrying_capacity`), the swarms enter a **Repelled Random Walk** state for $k$ ticks.

Similarly, when a swarm encounters an incompatible plant host (`diet_compatibility == 0.0`) without finding viable forage on the tile, the feeding subsystem marks `swarm.repelled = True` and sets `swarm.repelled_ticks_remaining = INCOMPATIBLE_DIET_REPULSION_TICKS` (defaulting to 2 ticks, calibrated in `phids.shared.constants`). This algorithmic deterrence breaks spatial arrestment and forces kinetic dispersal away from hostile or nutritionally barren flora.

### Biological Rationale

This serves as a dual computational surrogate for:

* Crowding-induced displacement: When too many grazers cram into a single patch, physical jostling forces the groups to scatter radially, expanding the foraging front and alleviating localized density pressure.
* Non-host rejection dispersal: Herbivores landing on unpalatable or non-host vegetation rapidly dismount and disperse under gustatory deterrence, preventing kinetic arrestment on non-viable flora.

## 4. Trophic Feeding & Functional Responses

$$E_{\text{consumed}} = \frac{a \cdot E_{\text{plant}}}{1 + a \cdot T_h \cdot E_{\text{plant}}} \cdot n_i$$

Where $a = \frac{\text{consumption\_rate}}{\text{velocity}}$ represents attack search efficiency, $T_h$ represents handling time per calorie, and $n_i$ is the population size of the co-located swarm.

!!! note "Scientific Progression: Linear Intake vs. Holling Type II Response"
    Earlier simulation versions modeled feeding as a strictly linear function of plant energy ($E_{\text{consumed}} = a \cdot E_{\text{plant}}$), assuming herbivores could digest infinite plant mass instantly at high densities. PHIDS incorporates Holling's Type II Functional Response incorporating handling time ($T_h$), recreating realistic biological saturation ceilings and preventing sudden, unnatural ecosystem collapses.

## 5. Trophic Anchoring & MVT Stochastic Departure (The Arrestment Reflex)

### I. The Arrestment Reflex

Prior to resolving the global navigation vectors generated by the chemotactic flow-field equations, the herbivore interaction architecture asserts a strict, short-circuiting heuristic. If the localized spatial hash detects that the swarm is co-located with non-depleted biomass that maps favorably against the species' `DietCompatibilityMatrix`, the execution pipeline triggers a conditional override.

When an animal discovers a highly profitable caloric patch, it transitions from a *navigational exploration* paradigm to a *stationary exploitation* paradigm. This is the **Arrestment Reflex**, which locks the swarm's kinetic momentum to a zero-vector state ($\Delta x = 0, \Delta y = 0$), transitioning the entity directly into a synchronous feeding phase.

### II. Deep Dive: Biologists (MVT & Bet-Hedging)

However, real organisms do not wait until a patch is completely barren before leaving. According to Optimal Foraging Theory, specifically **Charnov's Marginal Value Theorem (MVT)**, a forager should abandon a patch when the local intake rate drops below the expected average intake rate of the broader environment.

In PHIDS, this is modeled by continuously evaluating the swarm's recent `caloric_intake` against its baseline `metabolism_upkeep`.

If the intake exceeds the upkeep, the swarm is satiated and remains anchored. If the intake drops below the upkeep, the swarm enters a deficit. Rather than leaving immediately in an absolute binary fashion (which would create artificial, synchronized "pulse" migrations), the swarm exhibits **biological bet-hedging**. It evaluates a probabilistic departure curve based on the severity of the deficit. A slight deficit might trigger a small chance of departure (representing exploratory scouting), while a severe deficit triggers near-certain departure. This produces an incredibly realistic diffuse foraging behavior where swarms abandon patches while the plant is still alive (averaging 98.20% departure rate before total depletion in benchmarks), leaving a median biomass behind that sustains ecosystem resilience.

### III. Deep Dive: Mathematicians (The Logistic Sigmoid)

The stochastic departure is mathematically governed by a continuous logistic sigmoid function.
When $U > 0$ (Upkeep) and $I < U$ (Intake deficit), we define the ratio $R = \frac{I}{U}$.
The probability of departure $P(\text{depart})$ is calculated as:

$$P(\text{depart}) = \frac{1}{1 + e^{k(R - 1)}}$$

Where $k$ is the logistic steepness constant ($k = \text{MVT\_DEPARTURE\_SIGMOID\_STEEPNESS} = 5.0$).

* When $R = 1.0$ (Break-even), $P(\text{depart}) = 0.5$. (In practice, the system short-circuits to $0.0$ probability of departure if $R \ge 1.0$).
* As $R \to 0$ (Starvation), the exponent $k(R - 1)$ approaches $-5.0$, and $e^{-5.0} \approx 0.0067$, driving $P(\text{depart}) \to \frac{1}{1.0067} \approx 0.993$.

A standard uniform random variable $X \sim U(0, 1)$ is sampled; if $X < P(\text{depart})$, the swarm breaks its anchoring lock.

### IV. Deep Dive: Computer Scientists (JIT & Determinism)

Evaluating the chemotactic scalar field necessitates reading and interpolating data across numerous disparate tensor arrays (encompassing constitutive volatile plumes, attractant density matrices, and localized toxicity fields). The anchoring heuristic replaces this $O(M)$ tensor evaluation with a singular $O(1)$ scalar boolean check.

However, implementing stochastic processes within Numba's `@njit(cache=True)` kernels presents a severe challenge for simulation determinism (**Rule 01: Stochastic Replay Determinism**). If the JIT kernel calls internal PRNGs (e.g. `np.random.random()`), it desynchronizes the global seed state, breaking the ability to perfectly replay Zarr traces.

To resolve this, the MVT evaluation is implemented as a **Pure Function**. A single random float `rand_val` is generated in the Python interpreter scope using the controlled, globally-seeded PRNG, and is passed into the JIT kernel as a scalar parameter. The probabilistic logistic math adds approximately ~1-3ms of overhead per 100,000 swarms, a cost rendered completely negligible against the memory access overhead it bypasses.

## 6. Mitosis & Clonal Bifurcation

When an anchored swarm consumes immense amounts of energy, it converts the surplus into population. If $N_i \ge N_{split}$, the swarm physically divides.

### Algorithmic Resolution

The system executes a binary fission:

1. The parent swarm's population and energy are divided exactly in half ($N/2, E/2$).
2. A new `SwarmComponent` is allocated carrying the remaining half.
3. The new offspring swarm inherits identical phenotypic traits (consumption rate, metabolism).
4. The offspring is explicitly placed via a `_random_walk_step` in an adjacent tile.

### Biological Rationale

Symmetric partitioning conserves absolute biomass during the split. Forcing the offspring into an adjacent tile prevents immediate spatial re-coalescence. This physically models the division of a super-colony-such as insect hives branching off a new queen, or a massive grazing herd fracturing into two distinct pods under social pressure.

### Feeding & Attrition Dynamics

#### The Theoretical Model (Continuous Thought)

In a continuous biological model, herbivore populations grow or shrink based on net caloric intake versus metabolic burn, and suffer continuous attrition rates when feeding on heavily armored plants. A perfectly continuous solver allows for fractional survival (e.g., 0.4 of a herbivore remaining) and continuous caloric absorption.

#### The Numerical Mapping (Discrete Realization)

Because PHIDS operates a rigid Entity-Component-System (ECS) spatial hash, populations must remain strict integers, and metabolic accounting must strictly govern the "Attrition Trap" (starving while eating due to low digestibility).

##### Phase 1: Caloric Accounting (The Attrition Trap)

To simulate quantitative defenses (like high lignin), the digestibility modifier must scale the *gross* intake before baseline metabolism is paid.

1. **Gross Intake:** $\Delta e_{\text{raw}} = \text{bites\_taken} \times E_{\text{per\_bite}}$
2. **Digestion:** $\Delta e_{\text{real}} = \Delta e_{\text{raw}} \times \text{digestibility\_modifier}$
3. **Net Energy:** $E_{t+1} = E_t + \Delta e_{\text{real}} - \text{metabolism\_upkeep}$
*(If $\Delta e_{\text{real}}$ cannot cover the upkeep, the swarm mathematically loses energy despite feeding).*

##### Phase 2: Mechanical Attrition (Integer Enforcement)

To prevent "ghost fractions" from breaking the simulation constraints, physical damage taken from plant defenses is cast using a strict mathematical floor function:

$$\text{Casualties} = \lfloor \text{mechanical\_damage\_per\_bite} \cdot (1.0 - \text{resistance}_{\text{mechanical}}) \rfloor$$

Where:

- $\Delta e_{\text{raw}}$: Gross raw caloric intake extracted from the plant.
- $\Delta e_{\text{real}}$: Net energy actually digested and absorbed by the swarm.
- $\text{digestibility\_modifier}$: Scaler ($0.0 - 1.0$) representing constitutive defense reduction of calorie extraction.
- $\text{Casualties}$: The exact integer count of swarm members killed by physical trauma.
- $\text{mechanical\_damage\_per\_bite}$: Absolute damage values inflicted by physical armaments (e.g., thorns).
- $\text{resistance}_{\text{mechanical}}$: Herbivore counter-adaptation scaler ($0.0 - 1.0$) mitigating incoming physical damage.

## Co-Evolutionary Adaptations & Resistance Matrices

To counter plant defenses, the PHIDS engine supports formal evolutionary arms races through the `HerbivoreResistancesSchema` attached to the `HerbivoreSpeciesParams` (with the dictionary mapping `resistances`).

In nature, herbivores do not passively accept plant defenses; they co-evolve specialized adaptations to bypass them.

!!! info "Biological Context"
    **Mechanical Resistance:** Giraffes possess heavily keratinized, prehensile tongues and thick saliva, allowing them to strip acacia leaves completely ignoring massive thorns.
    **Chemical Resistance:** Monarch caterpillars have evolved to sequester the deadly cardiac glycosides of milkweed without taking cellular damage. Ruminants (like deer or cattle) have specialized foregut fermentation chambers utilizing symbiotic bacteria to break down tough lignins that other herbivores cannot digest.

These are represented by three primary parameters:

- `morphological_adaptation`: Resistance to physical trauma.
- `chemical_neutralization`: Metabolic ability to neutralize ingested active toxins.
- `digestive_efficiency`: Ability to extract calories from tough or high-lignin plant matter.

The resistances mapping allows swarms to mathematically mitigate incoming damage or digestibility penalties. A swarm with a `morphological_adaptation` (i.e. $\text{resistance}_{\text{mechanical}}$) of 0.9 will effectively ignore 90% of the damage from a thorny plant, giving them an exclusive ecological niche and a massive competitive advantage over non-resistant swarms.

---

## Data-Flow Matrix Specifications

### Conceptual Guide for General Observers

!!! note "Understanding the Data-Flow Matrix (Conceptual Metaphor)"
    Think of the table below as a slow-motion film strip tracking an herbivore swarm as it runs out of food and faces starvation.

    Animals burn a steady baseline of metabolic energy simply staying alive (basal metabolic rate). In our simulation, swarms do not instantly vanish when food is scarce; they survive by metabolizing internal caloric reserves. Only when those reserves are completely exhausted does mortality occur.

    * **Tick ($t_0, t_{24}, \dots$):** Simulation time steps grouped into 24-tick daily biological strides.
    * **State Columns:** Track swarm headcounts, caloric reserves, and minimum survival thresholds.
    * **Operation & Rule Column:** Explains the metabolic tax deducted and the resulting survival or starvation outcome.

    Every number in this table is validated directly against the simulation engine, ensuring that described ecological starvation kinetics reflect genuine runtime math.

### Scenario Dynamics in Words (Technical Overview)

This matrix models the deterministic starvation attrition of an isolated herbivore swarm trapped in a depleted biotope patch:

1. **Initial Sustenance ($t_0$):** A swarm of 10 individuals occupies a spatial tile with a shared caloric reserve of $E = 20.0$. Each individual requires a baseline survival buffer of $E_{\text{min}} = 1.0$, with a daily upkeep rate of $0.05$. Because caloric reserves exceed minimum metabolic requirements, the swarm is fully viable (`alive_mask` = 1.0).
2. **First Daily Metabolic Stride ($t_{24}$):** The simulation evaluates basal metabolic maintenance on 24-tick circadian stride boundaries. Over 24 ticks without ingested forage, maintenance costs equal: $\Delta E = \text{pop} \times E_{\text{min}} \times \text{upkeep\_rate} \times 24 = 10 \times 1.0 \times 0.05 \times 24 = 12.0$. Caloric reserves decline from $20.0$ to $8.0$. Because remaining energy exceeds zero ($E > 0$), all 10 individuals survive intact through the first day.
3. **Starvation Collapse ($t_{48}$):** At the second 24-tick stride boundary, maintenance metabolism again assesses a $12.0$ caloric deduction. With only $8.0$ units remaining, the required metabolic deficit cannot be met ($8.0 - 12.0 \le 0$). Caloric reserves drop to $0.0$, the population collapses from 10 to 0, and `alive_mask` switches to $0.0$.
4. **Computational & SIMD Invariant:** Swarm depopulation occurs without dynamic memory deallocation or object deletion in the hot path. The scalar `alive_mask = 0.0` gates subsequent movement, feeding, and spatial density aggregation into zero-cost operations across vectorized ECS sweeps.

### Herbivore 24-Tick Metabolic Stride & Starvation Attrition

Below is the verified Data-Flow Matrix for herbivore metabolic maintenance and starvation attrition over consecutive 24-tick daily stride cycles in an empty patch ($\text{pop} = 10, E_{\text{min}} = 1.0, \text{upkeep\_rate} = 0.05$, daily drain $= 10 \times 1.0 \times 0.05 \times 24 = 12.0$):

| Tick $t$ | `population` | `energy` | `energy_min` | `upkeep_drain` | `alive_mask` | Applied Vectorized Operation & Gate Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **$t_0$** | 10 | 20.0 | 1.0 | 0.0 | 1.0 | **Initial State:** Swarm occupies patch with caloric reserve above minimum threshold. |
| **$t_{24}$** | 10 | 8.0 | 1.0 | 12.0 | 1.0 | **Daily Metabolic Drain:** Stride boundary evaluates $\Delta E = -12.0$. Caloric reserve drops to 8.0. |
| **$t_{48}$** | 0 | 0.0 | 1.0 | 12.0 | 0.0 | **Starvation Collapse:** Second metabolic deduction exhausts reserve ($8.0 - 12.0 \le 0$). Swarm eradicated. |
