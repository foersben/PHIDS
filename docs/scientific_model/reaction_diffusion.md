---
type: scientific_model
title: Reaction-Diffusion & Partial Differential Equations
status: active
version: 0.1
description: Documentation for Reaction-Diffusion & Partial Differential Equations
  in the PHIDS framework.
tags:
- phids
- ecs
- performance
- chemotaxis
- python
timestamp: "2026-07-25T10:52:00Z"
resources:
- src/phids/engine/core/biotope.py
---

The dispersion of Volatile Organic Compounds (VOCs)-airborne signals used by flora to warn neighbors of herbivore attacks-is mathematically modeled in PHIDS using a discrete Reaction-Diffusion system.

## Biological and Physical Context

In nature, when a plant is damaged, it releases chemical compounds into the surrounding air. The concentration of these chemicals decreases as they spread outwards, a process driven by random molecular motion (diffusion) and air currents (advection). Simultaneously, these compounds naturally degrade or react with atmospheric elements over time (decay).

To simulate this without tracking billions of individual molecules, physics and chemistry employ **Partial Differential Equations (PDEs)**-specifically, Reaction-Diffusion equations.

## The Mathematical Model

To track the exact concentration of a scent in the air at any given moment, we must account for three competing forces: how quickly the scent is spreading outward, how quickly the wind is blowing it away, and how much new scent the plant is currently producing. If we add up the spread and the new emissions, and subtract the natural fading, we know exactly how the smell changes over time.

In analytical chemistry, this continuous balancing act is described by a parabolic Partial Differential Equation (PDE) for a substance concentration $C$:

$$\frac{\partial C}{\partial t} = D \nabla^2 C - \lambda C + Q$$

In this mathematical formulation, $\frac{\partial C}{\partial t}$ defines the rate of change of the chemical concentration over time. This temporal evolution is driven primarily by the diffusion term $D \nabla^2 C$, where $D$ represents the substance-specific diffusion coefficient and $\nabla^2$ denotes the continuous Laplacian operator (the second spatial derivative). The Laplacian strictly dictates how the volatile substance expands outward from areas of high local concentration to regions of lower density. Environmental clearance is encapsulated by the decay term $\lambda C$, representing the natural, continuous degradation of the chemical profile over time. Finally, $Q$ serves as the discrete source term, injecting raw mass into the system from plant entities actively synthesizing and emitting the compound.

### Discretization for Cellular Automata

Because PHIDS operates on a discrete grid with discrete time steps ($\Delta t$), the continuous PDE cannot be solved directly. Instead, it is approximated using a two-step computational fluid dynamics approach:

#### I. Implementation Mechanics

The biotope layer (`src/phids/engine/core/biotope.py`) handles volatile organic compounds (VOCs) and chemical signals using a two-tier operator loop.

**Step 1: Semi-Lagrangian Advection (Wind):**

Before a scent can spread smoothly outward, it is violently pushed by the wind. To calculate this efficiently, the engine asks a simple question for every cell on the grid: *"Where did the wind blowing over this spot come from?"* It traces the wind backwards, grabs the smell from that upwind location, and pulls it forward into the current cell.

Mathematically, for every cell, the engine traces a trajectory backward in time along a localized wind vector field to determine the upstream concentration, interpolating the value from the read buffer. If the per-cell wind vector is $\mathbf{u} = (u_x, u_y)$, the advected concentration at cell $(x, y)$ is sampled from $(x - u_x, y - u_y)$ in the previous tick's read-buffer.

$$\tilde{C}^{t}(x,y) = C^t(x - u_x, y - u_y)$$

**Step 2: Isotropic Gaussian Convolution:**

Once the wind has shifted the scent downwind, the scent naturally blurs and spreads equally in all directions. The engine achieves this by mathematically "smudging" each cell's concentration into its immediate neighbors, similar to applying a blur filter to a digital photograph.

The engine applies a discrete convolution step using a strictly odd-sized Gaussian kernel (5x5 by default). The pre-computed convolution avoids expensive transcendental operations inside the Numba kernel.

Let the advected 2D grid matrix of signal concentration at tick $t$ be $\tilde{C}^t$. The update for tick $t+1$ becomes:

$$C^{t+1} = \gamma \cdot (\mathcal{K}_{iso} * \tilde{C}^t) + Q^t$$

In the discrete algorithmic realization, $\mathcal{K}_{iso}$ represents an odd-sized Gaussian blur kernel (specifically a $5 \times 5$ matrix) that ensures strictly symmetric spatial dispersion. The operator $*$ denotes the 2D discrete spatial convolution function across the grid. Environmental clearance is approximated by $\gamma$, the discrete decay factor (e.g., $0.85$, meaning 15% of the total mass dissipates per tick). Finally, $Q^t$ is the source matrix where cells containing active, emitting plants have their concentration algebraically increased by a fixed emission rate, completing the step integration.

```mermaid
flowchart LR
    subgraph Step_1 ["Step I: Semi-Lagrangian Wind Advection"]
        A["Target Grid Cell (x, y)"] -->|Trace Backward in Time| B["Upwind Coordinates<br>(x - u*dt, y - v*dt)"]
        B -->|Bilinear Interpolation| C["Interpolated Signal Concentration Value<br><i>from Read Buffer (State_Read)</i>"]
    end

    subgraph Step_2 ["Step II: Center-Symmetric Diffusion & Cleansing"]
        C --> D["Apply Odd-Sized Symmetric Gaussian Kernel<br><i>(5x5 Centered Convolution Matrix)</i>"]
        D --> E["Apply Substance Cleansing Factor<br><i>Subtract Lambda Coefficient * Concentration</i>"]
        E --> F{"Value Below Truncation<br>Bound (Value < epsilon)?"}
        F -- Yes --> G["Hard Snap Grid Cell to Zero<br><i>Removes Floating-Point Underflows</i>"]
        F -- No --> H["Write Concentration to Write Buffer<br><i>State_Write(x, y)</i>"]
    end

    %% Class Allocations
    classDef stateData fill:#111b24,stroke:#00b8d4,stroke-width:2px,rx:6px,ry:6px;
    classDef coreSys fill:#141224,stroke:#b388ff,stroke-width:2px,rx:6px,ry:6px;
    classDef shortcut fill:#112214,stroke:#00e676,stroke-width:2px,rx:6px,ry:6px;

    class A,B,C,D stateData
    class E,H coreSys
    class F,G shortcut
```

#### II. Why It Is Solved This Way

Pure isotropic diffusion models chemical spread as a series of perfectly expanding, concentric circular uniform bubbles. In real-world ecosystems, wind completely alters this landscape.

Furthermore, from a numerical computing standpoint, applying an even-sized convolution kernel to a discrete grid introduces a sub-pixel spatial phase shift on every single tick. Over hundreds of simulation frames, this asymmetry causes the chemical signals to unnaturally drift down and to the right, corrupting the biological fidelity of the paths.

#### III. The Historical/Continuous Alternative

The traditional method uses an explicit finite-difference upwind scheme to solve the continuous advection-diffusion equation:

$$\frac{\partial C}{\partial t} + \vec{u} \cdot \nabla C = D \nabla^2 C$$

Explicit schemes are bound by the strict Courant-Friedrichs-Lewy (CFL) stability condition:

$$\Delta t \le \frac{\Delta x}{|\vec{u}|}$$

where $\Delta x$ represents the spatial resolution (or physical width) of a single grid cell.

If the wind speed spikes unexpectedly in a scenario, an explicit alternative collapses numerically, causing infinite chemical concentration spikes and system crashes.

#### IV. Computational Improvement

* **Complexity:** The semi-Lagrangian approach is *unconditionally stable*. It allows the simulation engine to utilize significantly larger time steps ($\Delta t$) without risk of numerical explosion, maintaining stable $O(W \times H)$ grid passes regardless of wind velocity.
* **Kernel Minimization:** Restricting the convolution step to a tight, center-symmetric 5x5 kernel reduces the memory footprint and limits array cache misses. This keeps the execution pipeline bound to the immediate L1/L2 cache lines of modern processor cores during vectorization.

#### V. Biological Modeling Realism

* **Anisotropic Plant Communication:** Plants communicate via airborne volatile organic compounds (VOCs)-such as releasing green leaf volatiles or jasmonates when chewed by herbivores to prime defensive enzyme synthesis in neighboring flora.
* **Realistic Signal Plumes:** By pairing wind-driven advection with symmetric diffusion, PHIDS accurately models directional, elongated chemical plumes. Downwind plants receive early warning signals and synthesize defenses long before upwind plants register any threat, perfectly mirroring canopy-level micro-climate communication patterns observed in forest ecology.

## Spatial Dispersion & Degradation Dynamics

Consider a localized emission event centered on a discrete biotope coordinate. At the initial tick ($t=0$), a plant entity releases a concentrated volatile pulse (e.g., $C^0_{1,1} = 100$). During the subsequent simulation frame ($t=1$), the two-tier execution pipeline applies isotropic Gaussian convolution, distributing mass outward to orthogonal neighbors while maintaining central concentration proportion. Environmental clearance then applies discrete exponential decay ($\gamma = 0.9$), reducing the total localized mass by 10% while establishing an expanded spatial plume footprint.

```mermaid
flowchart TD
    %% Base Styling
    classDef stepNode fill:#1e293b,stroke:#38bdf8,stroke-width:2px,color:#f8fafc,rx:8px,ry:8px;
    classDef mathNode fill:#312e81,stroke:#818cf8,stroke-width:2px,color:#f8fafc,rx:8px,ry:8px;

    t0["<b>Tick 0: Emission Pulse</b><br/>Center (1, 1) = 100.0"]:::stepNode
    conv["<b>Step 1: Isotropic Convolution Matrix</b><br/>Distribute 20% to orthogonal neighbors"]:::mathNode
    decay["<b>Step 2: Degradation Decay Factor (γ = 0.9)</b><br/>Apply 10% mass clearance penalty"]:::mathNode
    t1["<b>Tick 1: Expanded Plume State</b><br/>Center = 18.0, Orthogonal Neighbors = 18.0"]:::stepNode

    t0 --> conv --> decay --> t1
```

## Subnormal Float Mitigation

When solving diffusion equations computationally, the tails of the Gaussian distribution approach zero infinitely but never reach it. This creates matrices filled with "subnormal" floats (e.g., `1e-300`). Processors struggle to calculate arithmetic with subnormals, causing severe CPU bottlenecks.

To maintain performance, PHIDS strictly enforces **matrix sparsity** by clamping small values. After the decay step:

$$C^{t+1}[C^{t+1} < \varepsilon] = 0$$

Where $\varepsilon$ is a configurable threshold (e.g., `1e-4`).

## Alternatives Considered

### Agent-Based Scent Particles

An alternative approach would be to spawn individual ECS entities representing "scent particles" that move randomly. This accurately models Brownian motion but fails completely at ecological scale: simulating 10 million airborne molecules requires 10 million spatial hashes per tick, destroying the frame rate.

* *Methodological Advantage:* By vectorizing the concentration into a continuous grid layer and applying custom Numba JIT-compiled convolutions, mathematically accurate macro-dispersion is achieved in bounded time, regardless of how much substance is emitted.

## Stress-Induced Resource Reallocation (Senescence)

This is one of the most sophisticated survival mechanisms in botany, modeling Stress-Induced Senescence.

!!! info "Biological Context"
    When a plant is subjected to severe, prolonged stress-such as continuous herbivory, impending frost, or drought-it will actively break down the chlorophyll in its leaves and rapidly pull valuable resources (nitrogen, carbon, and sugars) deep into its root system or woody stems. To an approaching herbivore, the plant visually and chemically appears "dead" or nutritionally barren, prompting the herd to move on. Once the environmental stress passes, the plant flushes resources back into its canopy.

In PHIDS, this is modeled via the `resource_withdrawal` trigger action payload and its corresponding runtime scalar, `apparent_nutrition_factor`. When a trigger rule evaluates to true-either from direct grazing (`HerbivoreAttackInitiator`) or preemptively receiving neighbor VOC signals (`EnvironmentalSignalInitiator`) using discrete step thresholds or sigmoidal Hill kinetics ($\alpha_{\text{priming}}(C) = \frac{C^n}{K_d^n + C^n}$)-and dispatches this action, the plant's `apparent_nutrition_factor` (normally 1.0) drops to the specified level (e.g., 0.1). This suppression is maintained for a specific `withdrawal_duration` before naturally decaying over the `aftereffect` period. Instead of synthesizing a costly toxin, the plant uses `resource_withdrawal` to avoid consumption entirely.

!!! note "Scientific Progression: Heaviside Step vs. Sigmoidal Hill Priming"
    While baseline scenario triggers employ a binary Heaviside Step Function ($H(C - C_{\text{min}})$), real-world botanical signal perception operates via continuous, dose-dependent receptor binding kinetics. PHIDS supports sigmoidal Hill Equations ($\alpha = \frac{C^n}{K_d^n + C^n}$), where low ambient VOC concentrations partially prime MAP-kinase enzyme pathways without incurring massive toxin synthesis costs, committing to full defensive execution only as signal plumes saturate local receptors.

This scalar directly alters the attraction landscape *before* the Gaussian convolution kernel diffuses sensory layers in the flow-field module.

### Impact on Chemotaxis

See `docs/scientific_model/chemotaxis.md` for the exact mathematical effects on swarm navigation.
