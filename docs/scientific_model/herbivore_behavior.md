# Herbivore Behavior & Kinematics

Herbivore swarms represent the primary consumer tier in the PHIDS simulation. Their behaviors—movement, feeding, population scaling, and division—are carefully bounded by biological rules that produce macroscopic swarm dynamics without relying on expensive global computation.

## 1. Locomotion & Probabilistic Sampling

Swarms do not move in absolute straight lines toward a distant target. When sampling their Moore Neighborhood $\mathcal{N}(x,y)$ against the unified Flow Field $F_t$, they utilize **probabilistic softmax-like weighting**.

**Biological Rationale:**
In real ecological systems, individuals in a herd do not possess perfect information. If 1,000 herbivores all determined that coordinate (5,5) had the absolute highest gradient mathematically, and all moved there simultaneously, they would form a physically impossible singularity. By using probabilistic sampling weighted heavily toward the gradient peak, PHIDS naturally models the "diffuse foraging fronts" observed in grazing animals or hymenoptera (insects). The swarm as a whole moves *generally* toward the target, but individual entities exhibit slight variations.

## 2. Inertial Persistence (The Orthokinetic Rule)

A critical edge case occurs when the entire gradient is flat (values $< 1 \times 10^{-6}$). This implies the swarm is outside the sensory horizon of any plant or toxin.

If gradient ascent alone drove the system, the swarm would halt completely.

**Algorithmic Resolution:**
When $F_t(u,v) \approx 0$, the swarm relies on **movement inertia** stored from its previous tick (`last_dx`, `last_dy`).
- A 10:1 preference weight is given to continue moving in the current heading.
- If no previous heading exists, isotropic random dispersal (Random Walk) is applied.

**Biological Rationale:**
This emulates *orthokinesis*—directional persistence. An animal searching a barren landscape does not spin in circles; it maintains a general heading until it intersects a new scent trail or geographic feature.

## 3. Capacity Limits & Physical Repulsion

The biotope is a discrete grid. While multiple swarms can occupy the same $(x, y)$ coordinate, doing so infinitely violates spatial realism.

**Algorithmic Resolution:**
At the start of the interaction phase, PHIDS aggregates the total population of all swarms currently on a tile. If this sum exceeds the `TILE_CARRYING_CAPACITY` (e.g., 500 individuals), the swarms enter a **Repelled Random Walk** state for $k$ ticks.

**Biological Rationale:**
This is a computational surrogate for crowding-induced displacement. When too many grazers cram into a single patch, physical jostling forces the groups to scatter radially, expanding the foraging front and alleviating the localized density pressure.

## 4. Trophic Anchoring (The Arrestment Reflex)

When a swarm co-locates with a plant, it does not immediately move off the tile.

**Algorithmic Resolution:**
The system queries the Spatial Hash for entities at $(x,y)$. If it discovers a Plant Entity that is non-depleted and validated by the **Diet Compatibility Matrix** as a permitted food source, the swarm executes an **Anchoring** override.

**Biological Rationale:**
This models the *arrestment reflex*. An animal locating a highly dense food patch ceases long-distance locomotion to maximize caloric intake, staying in place until the resource is depleted or it is forced away by predators/toxins.

## 5. Mitosis & Clonal Bifurcation

When an anchored swarm consumes immense amounts of energy, it converts the surplus into population. If $N_i \ge N_{split}$, the swarm physically divides.

**Algorithmic Resolution:**
The system executes a binary fission:
1. The parent swarm's population and energy are divided exactly in half ($N/2, E/2$).
2. A new `SwarmComponent` is allocated carrying the remaining half.
3. The new offspring swarm inherits identical phenotypic traits (consumption rate, metabolism).
4. The offspring is explicitly placed via a `_random_walk_step` in an adjacent tile.

**Biological Rationale:**
Symmetric partitioning conserves absolute biomass during the split. Forcing the offspring into an adjacent tile prevents immediate spatial re-coalescence. This physically models the division of a super-colony—such as insect hives branching off a new queen, or a massive grazing herd fracturing into two distinct pods under social pressure.
