# Population Dynamics vs. Continuous Solvers

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

If $E_i < \text{Total Upkeep}$, the swarm suffers an **Energy Deficit**. Deficits manifest as immediate casualties. The population $N_i$ is reduced proportionately to the caloric shortfall, ensuring the swarm rapidly scales down to a biologically sustainable size rather than abruptly collapsing.

If $N_i \le 0$, the entity is scheduled for garbage collection at the end of the phase.

### 2. Reproduction from Surplus

If the swarm secures enough energy to fulfill its baseline viability ($E_{base} = N_i \cdot E_{min,i}$), the remaining *surplus* energy is converted into new individuals.

Let $c_i$ be the reproductive cost per offspring ($E_{min,i} \cdot \rho_i$, where $\rho_i$ is a divisor).

$$
\Delta N_i = \left\lfloor \frac{\max(0, E_i - E_{base})}{c_i} \right\rfloor
$$

### 3. Mitosis

Cellular division within a macroscopic swarm occurs when the cluster population reaches $N_i \ge N_{split}$, prompting a physical bifurcation into two discrete ECS entities that share the parent's accumulated energy.

## Numerical Example

Imagine a swarm of 10 herbivores with a baseline upkeep $m_i = 1.0$ and a reproduction cost $c_i = 5.0$.

1.  **Feeding Phase:** The swarm eats a plant, bringing its total energy $E_i$ to **35.0**.
2.  **Metabolism Phase:** The swarm pays its upkeep ($10 \times 1.0 = 10.0$).
3.  **Surplus Calculation:** The swarm has $35.0 - 10.0 = 25.0$ surplus energy.
4.  **Reproduction:** The swarm converts the surplus into $\lfloor 25.0 / 5.0 \rfloor = 5$ new offspring.
5.  **Tick Conclusion:** The swarm ends the tick with a population of **15** and $0.0$ surplus energy.

If $N_{split} = 15$, the swarm will divide into two swarms of 7 and 8 individuals at the same coordinate.

## Alternatives Considered

- **Continuous-Time ODE Solvers (Lotka-Volterra):** The classic Lotka-Volterra predator-prey equations ($\frac{dx}{dt} = \alpha x - \beta xy$) model the rate of change of continuous populations.
    - *Why rejected:* ODEs treat populations as perfectly mixed, homogeneous continuous variables ($x = 42.5$ rabbits). They cannot capture discrete, localized spatial events, such as a specific herd of 10 herbivores navigating around a toxic plant at coordinate $(4, 12)$.
    - *Our advantage:* The discrete ECS formulation provides the spatial granularity required for physical movement, local chemical triggers, and density-dependent crowding (e.g., cell capacity repulsion) while preserving mathematical determinism.
