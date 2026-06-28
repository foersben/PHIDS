---
type: technical_architecture
title: "Trophic Optimizer"
status: active
version: 0.1
description: "Documentation for Trophic Optimizer in the PHIDS framework."
---

# Automated Hyperparameter Tuning: The Trophic Optimizer

Finding stable multi-species balance in a spatial discrete-event engine like PHIDS is exceptionally difficult. The parameter space of PHIDS is highly non-linear, discontinuous, and rugged. A tiny adjustment to a single species' metabolism can trigger an immediate, cascading trophic collapse. To solve this, PHIDS includes a native tuning pipeline powered by SciPy's Differential Evolution.

## Why Differential Evolution Wins

Finding stable parameters in PHIDS means searching a continuous space of floating-point numbers (metabolic steps, diffusion coefficients, decay constants, and consumption rates). Alternative optimization strategies fail due to the fundamental architecture of this landscape:

### 1. Simple Random Walk (Fails due to High Dimensionality)
* **The Problem:** In a scenario with 10 species and multiple chemical triggers, you are optimizing dozens of coupled dimensions simultaneously.
* **Why it fails:** The volume of the parameter space grows exponentially with the number of dimensions. The actual region of stability is a microscopic hyper-volume. A random walk has a near-zero statistical probability of ever stumbling into it.

### 2. Simulated Annealing (Fails due to Local Optima Traps)
* **The Problem:** Simulated Annealing tracks a single candidate solution through the parameter space.
* **Why it fails:** The PHIDS landscape is heavily peppered with deceptive local optima (e.g., finding a state where only one plant and one herbivore survive). Simulated Annealing easily gets trapped in these dead ecosystems.

### 3. Basic Genetic Algorithm (Fails due to Binary Constraints)
* **The Problem:** Traditional GAs often rely on discrete or binary representations of chromosomes.
* **Why it fails:** Biological rates are continuous variables. Splitting a float into discrete bits lacks the granularity to fine-tune delicate, coupled feedback loops.

### 4. SciPy's Differential Evolution (The Perfect Match)
* **Real-Valued Vectors:** DE operates natively on vectors of continuous floating-point numbers.
* **Self-Adaptive Mutations:** DE mutates candidate solutions by adding the weighted difference between two random population members. If the population is far apart, steps are large. As the population converges, steps become microscopic.
* **Parallel Population Search:** By evaluating a parallel pool of 20 genomes over 80x80 spatial matrices using multi-core execution, it successfully map-reduces stochastic variance.

## Defining the "Goldilocks" Configuration

In the context of PHIDS, a "Goldilocks" configuration is an explicit input parameter set where the localized spatial actions of entities yield a long-running, self-sustaining macroscopic ecosystem.

### 1. Absolute Termination Avoidance
The primary constraint is that the configuration must run completely through its execution window, avoiding all early error termination triggers ($Z_2 - Z_7$):
* **No Extinctions:** No flora or herbivore drops to a population of zero.
* **No Runaway Growth:** No species undergoes an uncontrolled trophic explosion breaching maximum carrying capacities.

### 2. Emergent Lotka-Volterra Oscillations
Rather than freezing into static population counts, a Goldilocks configuration achieves dynamic, localized patch balance resembling a smooth Lotka-Volterra wave.

On the 80x80 lattice, this manifests as a shifting mosaic:
1. Herbivores discover dense flora, consume biomass, and reproduce.
2. Flora activate multi-level defenses (VOC alerts, mycorrhizal signals, tissue toxins).
3. Herbivores disperse to clear zones, allowing the grazed patch to regenerate.

The system loops through these feedback states indefinitely, maintaining a low global Coefficient of Variation (CV) because localized boom-and-bust cycles balance out.

## Tuning Constraints & Architectural Implementation

The optimization loop executes headless evaluations across `ProcessPoolExecutor` workers to maximize throughput.

### Train Small, Run Large
To keep optimization computationally cheap, fitness functions can be evaluated on a smaller grid (e.g., 40x40). Because the engine utilizes spatial hashes and local neighborhoods, local density rules scale perfectly to massive matrices (100x100) after tuning.

### Mycorrhizal Network Settings
For optimization containing multiple interconnected niches, strict isolation is recommended (`mycorrhizal_inter_species = False`). If pioneer species can broadcast alarms into the entire root network, the map floods with toxins prematurely.

### CLI Integration
The `TrophicOptimizer` is seamlessly integrated into the PHIDS CLI:

```bash
uv run phids tune examples/eternal_canopy_blueprint.json --grid-size 80 --ticks 2500 --samples 20 --out examples/optimized_canopy.json
```
