# Chemotaxis & Flow Fields

Herbivore swarms navigate the PHIDS biotope via a unified scalar guidance field, simulating a sensory-driven process called **chemotaxis**.

## Biological and Physical Context

**Chemotaxis** is the phenomenon whereby somatic cells, bacteria, and other single-cell or multicellular organisms direct their movements according to certain chemicals in their environment.

In nature, organisms do not possess a top-down, global map of the world. They cannot calculate the most efficient Euclidean path to a food source three miles away while simultaneously avoiding a predator blocking a narrow mountain pass. Instead, they sense local chemical gradients—moving towards higher concentrations of attractants (food, mating pheromones) and away from repellents (toxins, predators).

By modeling chemotaxis, PHIDS ensures swarm navigation is inherently local, imperfect, and biologically plausible.

## The Unified Flow Field

Rather than solving a separate navigation problem for every individual herbivore swarm (e.g., $N$ swarms calculating paths across an $M \times M$ grid), PHIDS constructs a single **Flow Field** $F_t(x, y)$ at the beginning of each tick $t$.

This scalar lattice is a spatial superposition of two primary potentials:

1.  **Attractants ($E_t$):** The aggregate caloric energy of all flora species.
2.  **Repellents ($T_t$):** The aggregate concentration of localized defensive toxins emitted by flora.

### Mathematical Formulation

The baseline gradient at cell $(x, y)$ before propagation is computed as:

$$
G_t(x,y) = \alpha E_t(x,y) - \beta \sum_k T_{k,t}(x,y)
$$

Where:

- $E_t(x,y)$ is the total plant energy available at the coordinate.
- $T_{k,t}(x,y)$ is the concentration of the $k$-th toxin channel.
- $\alpha, \beta$ are non-negative weighting constants.

To create an "influence map" that swarms can detect from a short distance away, this baseline gradient undergoes a rapid, one-pass local 4-neighbor propagation (spreading) with a steep decay coefficient $\delta$ (e.g., $0.5$).

### The Gradient Ascent

A swarm located at $(x, y)$ determines its next position by evaluating the Flow Field $F_t$ in its immediate **Moore Neighborhood** $\mathcal{N}(x,y)$ (the current cell plus its 8 adjacent cells: North, South, East, West, and the four diagonals).

The chosen transition $(x', y')$ satisfies the condition:

$$
(x',y') = \operatorname*{arg\,max}_{(u,v) \in \mathcal{N}(x,y)} F_t(u,v)
$$

Stochastic tie-handling breaks equivalencies when multiple neighbors share the maximum gradient.

## Numerical Example

Imagine a swarm at center coordinate `(1, 1)` evaluating its Moore neighborhood in a simplified subset of the Flow Field $F_t$:

**Flow Field Segment:**
$$
\begin{bmatrix}
0.5 & 1.2 & 2.1 \\
0.1 & \mathbf{0.8} & 1.5 \\
0.0 & 0.4 & 0.9
\end{bmatrix}
$$

The swarm is located at the center cell `(1,1)` with a scalar value of **$0.8$**.

1.  The swarm evaluates all 9 cells (including its current location).
2.  The maximum value within $\mathcal{N}(1,1)$ is **$2.1$** at coordinate `(0, 2)` (Top-Right relative to the swarm).
3.  The swarm executes a movement to `(0, 2)`.

If the center cell `(1,1)` had the highest value (e.g., it was currently situated on a high-energy plant), the swarm would remain stationary, an act defined as **Anchoring**.

## Alternatives Considered

- **A* (A-Star) or Dijkstra Pathfinding:** Calculating optimal, obstacle-avoidant paths from every swarm to the nearest food source.
    - *Why rejected:* Classic pathfinding scales poorly. Calculating paths for hundreds of swarms across a dynamic grid per tick would bottleneck the CPU, creating a computational complexity of $O(N \cdot M^2)$. Furthermore, swarms lack "global knowledge" of the map; their navigation is inherently sensory-driven.
    - *Our advantage:* The unified Flow Field is calculated exactly *once* per tick via Numba JIT compilation. Every swarm simply samples its immediate adjacent cells via O(1) array reads. This perfectly mimics biological sensory constraints while maintaining extreme computational efficiency.

## Zero-Gradient Navigation (The Isotropic Search)

A critical edge case in spatial ecology occurs when an organism is entirely outside the sensory horizon of any resource or predator. Mathematically, this happens when the entire Moore neighborhood evaluates to zero:

$$
\forall (u,v) \in \mathcal{N}(x,y), \; F_t(u,v) = 0.0
$$

If a swarm relied strictly on gradient ascent, a zero-gradient would result in indefinite paralysis (anchoring in an empty void).

In biological systems, when an organism loses a scent trail, it transitions from directed movement (taxis) to an undirected, exploratory movement (kinesis) to maximize the probability of intersecting a new gradient.

**Algorithmic Resolution:**
When PHIDS evaluates a zero-gradient neighborhood, the swarm enters a **Random Walk** state. It selects a neighboring cell from a uniform random distribution, effectively performing an isotropic search until it re-enters the active Flow Field. This behavior is also deployed when swarms are actively repelled by incompatible flora or localized toxins, forcing them to disperse blindly until they secure a safe sensory anchor.
