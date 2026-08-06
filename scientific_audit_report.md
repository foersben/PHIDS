# Scientific Model Audit Report

## 1. Undefined or Orphaned Variables
After parsing the LaTeX math blocks ($$...$$) across the `docs/scientific_model/` directory, the following variables were found in equations but lacked explicit definitions in the surrounding prose:

- **`population_dynamics.md`**: The variable $\rho_i$ is mentioned as a divisor in $c_i = E_{min,i} \cdot \rho_i$, but what $\rho_i$ biologically represents (e.g., reproductive efficiency or mass scaling) is not defined.
- **`population_dynamics.md`**: $E_{min,i}$ is used in the baseline viability calculation ($E_{base} = N_i \cdot E_{min,i}$), but is never explicitly defined as the minimum energy requirement per individual.
- **`population_dynamics.md`**: In the Weibull hazard function equation $\mu(A) = \frac{k}{\lambda}(\frac{A}{\lambda})^{k-1}$, the variables $k$ (shape parameter) and $\lambda$ (scale parameter) are entirely undefined.
- **`reaction_diffusion.md`**: In the CFL stability condition $\Delta t \le \frac{\Delta x}{|\vec{u}|}$, the spatial resolution variable $\Delta x$ is not explicitly defined in the text.
- **`mathematical_framework.md`**: In the equation $\Delta E_{i\leftarrow j} = \min( \frac{r_i}{\max(1, v_i)} N_i, E_j )$, the variable $E_j$ is not explicitly defined in the surrounding paragraph (though it can be inferred as plant energy).

## 2. Mathematical vs. Implementation Discrepancies
Cross-referencing the documented mathematical equations with the actual Numba/Python implementations revealed the following 'hallucinations' or drift:

- **reaction_diffusion.md**: The documentation claims a $5 \times 5$ Gaussian kernel is used for isotropic diffusion (`\mathcal{K}_{iso}`), but the actual implementation in `src/phids/engine/core/biotope.py` defaults to a $3 \times 3$ kernel (`_KERNEL_SIZE: int = 3`).
- **`chemotaxis.md` / `mathematical_framework.md`**: The documentation describes Flow Field generation as a straightforward matrix superposition and propagation decay. However, the actual implementation (`src/phids/engine/core/flow_field.py`) uses an iterative **Jacobi relaxation** solver (`_propagate_iteration_jit` and `_propagate_boundaries_jit`) that iterates until `max_diff` converges below a tolerance or a maximum step count is reached. The documentation completely hallucinates a simple one-pass propagation.
- **`herbivore_behavior.md`**: The text claims that if the population on a tile exceeds `TILE_CARRYING_CAPACITY` (e.g., 500 individuals), swarms enter a **Repelled Random Walk** state for $k$ ticks. However, checking `src/phids/engine/systems/interaction/movement.py` (`_resolve_swarm_movement`), there is no stateful '$k$ ticks' timer for repulsion. Repulsion simply triggers an immediate random walk step (`_random_walk_step`) on the current tick if the density is high.
- **`reaction_diffusion.md`**: The document outlines the PDE for continuous Reaction-Diffusion (including $\nabla^2 C$). It then claims a "Semi-Lagrangian Advection (Wind)" trace-back mechanism interpolates values from the read buffer using bilinear interpolation (indicated in the Mermaid diagram). However, `src/phids/engine/core/biotope.py` (`_numba_advect_signal_layer_pow2`) uses a **stochastic/nearest-neighbor** probabilistic advection approximation (comparing `random.random()` against fractional components like `val_x0 * dx`) rather than true bilinear interpolation.

## 3. Missing Diagrams for Complex Spatial Relationships
The following spatial processes are explained entirely in dense text and require Mermaid.js or mathematical diagrams for clarity:

- **Stochastic Polar Seed Dispersal (`flora_and_symbiosis.md`)**: The translation from radial dispersion ($d \sim U$, $\delta_\perp \sim \mathcal{N}$) back to a discrete Cartesian grid ($x_{target}, y_{target}$) is highly visual but lacks any diagram showing the wind vector, perpendicular drift, and bounding box.
- **Von-Neumann Flow Field Sampling (`chemotaxis.md` / `movement.py`)**: The probability-weighted gradient ascent (Stochastic Taxis) and isotropic search (Random Walk) on flat gradients are purely text-based. A state machine diagram mapping the transition between Directed Taxis $\leftrightarrow$ Isotropic Kinesis based on $\nabla F_t$ would resolve this.
- **Mycorrhizal Network Topologies**: If Mycorrhizal connections operate on Manhattan distance adjacency (as noted in project memory), the topology of how roots link and transfer energy needs a structural graph diagram, rather than just text descriptions.
