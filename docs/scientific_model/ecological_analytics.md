# Ecological Analytics & Evaluation

PHIDS converts simulation ticks into comparable, analytical artifacts. The primary method for evaluating a scenario's success or failure is through longitudinal population and energy tracking.

## 1. The Lotka-Volterra Paradigm

The core engine tracks aggregate metrics—total flora energy, total flora population, and total herbivore population—at the conclusion of every tick.

These aggregates are directly inspired by the **Lotka-Volterra Equations**, standard continuous-time predator-prey models defined by:

$$
\begin{aligned}
\frac{dx}{dt} &= \alpha x - \beta xy \\
\frac{dy}{dt} &= \delta xy - \gamma y
\end{aligned}
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

## 3. Simulation & Batch Diagrams

The UI Control Center visualizes these metrics via several primary tools tailored for either the live simulation view or aggregate batch processing.

### Live Simulation Diagrams

- **Live Dashboard Canvas:** Displays an immediate top-down 2D array representation of the `GridEnvironment` (the cellular automata).
    - Green pixels denote Flora energy density.
    - Red pixels denote Herbivore swarms.
    - Overlays visualize airborne signal diffusion (blue) or localized toxins (fuchsia).
- **Telemetry Chart:** A longitudinal line graph tracking the aggregate populations and energies over time. It visually maps the cyclic oscillations. If the red line (herbivores) spikes massively and then flatlines to zero while the green line (flora) continues to grow exponentially, the user immediately recognizes a $Z_5$ termination event (Herbivore Extinction).

### Batch Processing Diagnostics

When running large Monte Carlo batches to evaluate scenario stability, tracking an average population line is insufficient. PHIDS offers robust statistical plotting presets:

- **Stacked Biomass Proxy:** A normalized area chart displaying the ratio of total ecosystem energy held by Flora versus Herbivores. It is crucial for visualizing the total carrying capacity of the ecosystem and whether energy is smoothly passing up the trophic chain or becoming trapped.
- **Phase Space:** A scatter plot mapping Flora Population ($X$) against Herbivore Population ($Y$) across time. In a perfectly stable Lotka-Volterra ecosystem, this forms a closed, repeating orbital loop. If the ecosystem crashes, the path spirals into the origin $(0,0)$.
- **Collapse Risk Focus:** A survival probability curve (Kaplan-Meier estimator). It measures the probability that a scenario reaches a specific tick $T$ without triggering an extinction or runaway termination ($Z_2 - Z_7$). This is the primary metric for proving scenario stability.
- **Defense Economy Ratio:** A line chart isolating the specific plant deaths tagged as `death_defense_maintenance`. It visualizes the metabolic burden of synthesizing toxins; if this ratio spikes, the flora are over-producing defenses and starving themselves to death.
- **Herbivore Pressure Focus:** Maps total herbivore population against specific flora fatalities tagged as `death_herbivore_feeding`. This proves definitively whether declining plant populations are due to active predation or simply poor baseline growth constraints.

### Tabular Ledger

A data grid providing the exact numeric breakdown per tick. This is powered by `Polars` for extreme performance, separating the specific death causes so scientists can definitively prove *what* caused the population collapse at Tick 450.
