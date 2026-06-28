---
type: concept
title: "Introduction to Scenarios"
status: active
version: 1.0
description: "Overview of scenario design, complexity, and calibration in the PHIDS simulation framework."
---

# Introduction to Scenarios

In the study of computational ecology, the greatest challenge is managing the sheer volatility of natural systems. The parameter space of a spatial ecosystem is a chaotic, highly non-linear landscape. A minor $1\%$ tweak to a single herbivore's metabolic rate or a plant's regeneration speed can be the absolute boundary between eternal multi-species balance and immediate, cascading trophic collapse.

The **Scenarios** module in PHIDS upgrades the framework from a simple "run-and-observe" simulator into a **generative biology tool**. It provides the interfaces, constraints, and optimization pipelines needed to design, validate, and calibrate complex ecological experiments.

---

```mermaid
graph TD
    Author["1. Scenario Authoring<br>(Define Schema, Diet, & Defense Triggers)"] --> Examples["2. Curated Examples<br>(Run Blueprint Baseline Archetypes)"]
    Examples --> Calibration["3. Scenario Calibration<br>(Calibrate Stable Attractors via Trophic Optimizer)"]
    Calibration --> Generative["Endless Balanced Simulation Run"]
```

---

## Exploring the Scenarios Module

To guide your workflow from initial design to self-sustaining execution, the Scenarios documentation is partitioned into three key guides:

### 1. [Scenario Authoring & Schema](scenario_authoring.md)

Understand how to define your custom ecosystem configurations. This guide details:

* The Pydantic validation schema (`SimulationConfig`) ensuring configuration integrity before boot.
* The **Rule of 16** constraint, which limits flora, herbivores, and chemical substances to pre-allocated static cache lines, avoiding dynamic memory allocation latency during hot execution loops.
* How to define the **Diet Compatibility** and **Biochemical Trigger** matrices to construct complex trophic relationships.

### 2. [Curated Examples](curated_examples.md)

Inspect pre-configured blueprints designed to demonstrate specific ecological features:

* **The Eternal Canopy:** An complex, balanced forest biotope showing stabilized Lotka-Volterra wave propagation.
* **Trophic Collapse Scenario:** A demonstration of ecological breakdown when herbivore consumption rates breach flora regeneration thresholds.
* **Volatile Warning Cascade:** A scenario highlighting chemical atmospheric warning diffusion across spatial grids.

### 3. [Scenario Calibration (Trophic Optimizer)](trophic_optimizer.md)

Discover how the framework uses SciPy's Differential Evolution to find stable parameters autonomously:

* **Optimization Search:** Why genetic/evolutionary search beats Random Walk and Simulated Annealing in rugged biological landscapes.
* **The Goldilocks Configuration:** The strict mathematical criteria (termination avoidance and low coefficient of variation) that define a stable ecosystem.
* **The 'Train Small, Run Large' Paradigm:** How to optimize settings on a $40 \times 40$ matrix and scale them to a massive $100 \times 100$ spatial hash.
