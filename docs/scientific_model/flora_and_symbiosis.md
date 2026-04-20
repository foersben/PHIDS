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
1.  **Calm Air ($Wind \approx 0$):** A bounded annulus is generated around the parent, defined by $r_{min}$ and $r_{max}$. A random polar angle $\theta$ is chosen. The seed falls at $(x + r \cos \theta, y + r \sin \theta)$.
2.  **Wind-Active Air:** If wind is present, the model switches to an anemochorous kernel. It samples a Gaussian distribution aligned to the continuous wind vector $(Wind_X, Wind_Y)$, scaled by the seed's terminal velocity and drop height.
3.  **The Exclusion Zone:** Seeds *cannot* germinate if they land on an already occupied grid cell. If the target coordinate is occupied, the reproductive energy is spent, but no new entity is generated.

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

1.  If Plant A is attacked, it triggers a signaling substance (Section 5.1, Reaction-Diffusion).
2.  Plant A begins emitting VOCs into the air above it.
3.  Simultaneously, Plant A injects the exact same signal concentration *directly* into the connected root node of Plant B.

Because the signal travels over the Graph Structure of the Mycorrhiza at $t_{velocity}$ (hops per tick), it propagates significantly faster than atmospheric diffusion.

Plant B receives the chemical warning of Herbivore predation without having to wait for the Gaussian convolution kernel to disperse the signal through the air, allowing Plant B to synthesize its own localized Toxins preemptively.

## 3. Death & Telemetry Causation

In older OOP simulations, death is a simple variable boolean `True/False`. In PHIDS, biological extinction provides explicit causal telemetry.

Whenever a plant energy value falls beneath its survival threshold, it is scheduled for garbage collection by the ECS framework. Crucially, the engine tags exactly *why* the energy plummeted via the `last_energy_loss_cause` tracker:

-   **`death_reproduction`**: The plant over-extended dropping seeds.
-   **`death_mycorrhiza`**: The plant died trying to pay the cost of connecting to a fungal network.
-   **`death_defense_maintenance`**: The plant successfully synthesized a defensive toxin but lacked the caloric intake to maintain it.
-   **`death_herbivore_feeding`**: The plant was completely stripped of energy by a grazing swarm.
-   **`death_background_deficit`**: General starvation due to low growth or high thresholds.

These tags are essential for interpreting whether an ecosystem collapsed due to predation or metabolic mismanagement.
