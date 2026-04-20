# Ecological Analytics & Evaluation

PHIDS converts simulation ticks into comparable, analytical artifacts. The primary method for evaluating a scenario's success or failure is through longitudinal population and energy tracking.

## 1. The Lotka-Volterra Paradigm

The core engine tracks aggregate metrics—total flora energy, total flora population, and total herbivore population—at the conclusion of every tick.

These aggregates are directly inspired by the **Lotka-Volterra Equations**, standard continuous-time predator-prey models defined by:

$$
\frac{dx}{dt} = \alpha x - \beta xy
$$
$$
\frac{dy}{dt} = \delta xy - \gamma y
$$

Where:

- $x$: Prey population (Flora).
- $y$: Predator population (Herbivores).
- $\alpha, \beta, \gamma, \delta$: Growth, predation, mortality, and assimilation rates.

### The Purpose of Tracking

While PHIDS is a discrete spatial simulation and *not* a continuous ODE solver (see [Population Dynamics](population_dynamics.md)), the macroscopic emergent behavior of the grid should still resemble classical Lotka-Volterra dynamics.

A successful, stable scenario will exhibit **Cyclic Oscillations** (Boom-and-Bust cycles):
1.  **Boom:** Flora energy grows, enabling high reproduction.
2.  **Explosion:** Herbivores discover the dense flora, feed rapidly, and undergo massive mitosis (splitting).
3.  **Bust:** The enormous herbivore swarm overgrazes the flora, causing a precipitous drop in plant energy.
4.  **Starvation:** With no food left, herbivores suffer severe metabolic attrition and die off.
5.  **Recovery:** The few remaining plants, now free of predators, begin to grow again.

If a scenario does not cycle, it inevitably hits a **Termination Condition**.

## 2. Termination Protocols ($Z_1$ - $Z_7$)

The engine integrates continuous checks against operational bounds:

- **Max Duration ($Z_1$)**: Cap on ticks. The scenario successfully ran its course without collapsing.
- **Extinctions ($Z_2, Z_3, Z_4, Z_5$)**: Target or global population collapse. A species was entirely wiped out by either starvation or predation.
- **Runaway Growth ($Z_6, Z_7$)**: Exceeding specified energy/population carrying capacities. The biological parameters were completely unbalanced, causing infinite reproduction.

Termination flags provide vital context as to *why* a particular experimental model collapsed, allowing for deeper scientific comparison across scenario families.

## 3. Data Representation

The UI Control Center visualizes these Lotka-Volterra-like metrics via three primary tools:

### Live Dashboard Canvas
Displays an immediate top-down 2D array representation of the `GridEnvironment` (the cellular automata).
- **Green pixels:** Flora energy density.
- **Red pixels:** Herbivore swarms.
- **Overlays:** Visualize airborne signal diffusion (blue) or localized toxins (fuchsia).

### Telemetry Chart
A longitudinal line graph tracking the aggregate populations and energies over time. It visually maps the cyclic oscillations. If the red line (herbivores) spikes massively and then flatlines to zero while the green line (flora) continues to grow exponentially, the user immediately recognizes a $Z_5$ termination event (Herbivore Extinction).

### Tabular Ledger
A data grid providing the exact numeric breakdown per tick. This is powered by `Polars` for extreme performance, separating the specific death causes (`death_reproduction`, `death_mycorrhiza`, `death_defense_maintenance`, `death_herbivore_feeding`, `death_background_deficit`) so scientists can definitively prove *what* caused the population collapse at Tick 450.
