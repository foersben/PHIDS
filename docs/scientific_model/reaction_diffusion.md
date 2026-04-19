# Reaction-Diffusion & Partial Differential Equations

The dispersion of Volatile Organic Compounds (VOCs)—airborne signals used by flora to warn neighbors of herbivore attacks—is mathematically modeled in PHIDS using a discrete Reaction-Diffusion system.

## Biological and Physical Context

In nature, when a plant is damaged, it releases chemical compounds into the surrounding air. The concentration of these chemicals decreases as they spread outwards, a process driven by random molecular motion (diffusion) and air currents (advection). Simultaneously, these compounds naturally degrade or react with atmospheric elements over time (decay).

To simulate this without tracking billions of individual molecules, physics and chemistry employ **Partial Differential Equations (PDEs)**—specifically, Reaction-Diffusion equations.

## The Mathematical Model

The continuous parabolic PDE describing this phenomenon for a substance concentration $C$ is:

$$
\frac{\partial C}{\partial t} = D \nabla^2 C - \lambda C + Q
$$

Where:

- $\frac{\partial C}{\partial t}$: The change in concentration over time.
- $D \nabla^2 C$: The diffusion term (Laplacian operator), describing how the substance spreads from areas of high concentration to low concentration.
- $\lambda C$: The decay term, representing the natural degradation of the chemical.
- $Q$: The source term, representing actively emitting plants.

### Discretization for Cellular Automata

Because PHIDS operates on a discrete grid with discrete time steps ($\Delta t$), we cannot solve the continuous PDE directly. Instead, we approximate it.

The spatial diffusion ($\nabla^2 C$) is approximated using an **isotropic Gaussian convolution kernel**.

Let the 2D grid matrix of signal concentration at tick $t$ be $C^t$. The update for tick $t+1$ becomes:

$$
C^{t+1} = \gamma \cdot (\mathcal{K}_{iso} * C^t) + Q^t
$$

Where:

- $\mathcal{K}_{iso}$ is a $3 \times 3$ Gaussian blur kernel.
- $*$ denotes the 2D discrete convolution.
- $\gamma$ is the decay factor (e.g., $0.85$, meaning 15% dissipates per tick).
- $Q^t$ is the matrix where cells containing active emitting plants have their concentration increased by a fixed emission rate.

### Advection (Wind)

To simulate wind, we apply a semi-Lagrangian backtracing step before diffusion. If the wind vector is $\mathbf{u} = (u_x, u_y)$, the concentration at cell $(x, y)$ is sampled from $(x - u_x, y - u_y)$ in the previous tick's read-buffer.

$$
\tilde{C}^{t}(x,y) = C^t(x - u_x, y - u_y)
$$

The full update is then the convolution of the advected field $\tilde{C}^{t}$.

## Numerical Example

Imagine a $3 \times 3$ grid segment. The center cell $(1,1)$ contains a plant actively emitting a signal.

**Tick 0:**
$$
C^0 =
\begin{bmatrix}
0 & 0 & 0 \\
0 & 100 & 0 \\
0 & 0 & 0
\end{bmatrix}
$$

Assume a simplified discrete Laplacian convolution kernel $\mathcal{K}$ that distributes 20% of a cell's value to its 4 orthogonal neighbors, keeping 20% in the center. Assume decay factor $\gamma = 0.9$ and no new emission ($Q=0$).

**Tick 1 (After Convolution):**
$$
\mathcal{K} * C^0 =
\begin{bmatrix}
0 & 20 & 0 \\
20 & 20 & 20 \\
0 & 20 & 0
\end{bmatrix}
$$

**Tick 1 (After Decay $\gamma = 0.9$):**
$$
C^1 =
\begin{bmatrix}
0 & 18 & 0 \\
18 & 18 & 18 \\
0 & 18 & 0
\end{bmatrix}
$$

The signal has dispersed outward while losing 10% of its total mass to decay.

## Subnormal Float Mitigation

When solving diffusion equations computationally, the tails of the Gaussian distribution approach zero infinitely but never reach it. This creates matrices filled with "subnormal" floats (e.g., `1e-300`). Processors struggle to calculate arithmetic with subnormals, causing severe CPU bottlenecks.

To maintain performance, PHIDS strictly enforces **matrix sparsity** by clamping small values. After the decay step:

$$
C^{t+1}[C^{t+1} < \varepsilon] = 0
$$

Where $\varepsilon$ is a configurable threshold (e.g., `1e-4`).

## Alternatives Considered

- **Agent-Based Scent Particles:** We could spawn individual ECS entities representing "scent particles" that move randomly.
    - *Why rejected:* Tracking millions of particles per tick destroys the $O(1)$ scaling constraint of the engine.
    - *Our advantage:* By vectorizing the concentration into a continuous grid layer and applying `scipy.signal.convolve2d`, we achieve mathematically accurate macro-dispersion in bounded time, regardless of how much substance is emitted.
