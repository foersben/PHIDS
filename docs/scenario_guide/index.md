---
type: concept
title: Scenarios Module Overview
status: active
version: 1.0
description: Overview of scenario authoring, curated example blueprints, and DSE optimization pipelines.
tags:
- phids
- scenarios
- dse
- blueprints
timestamp: "2026-07-26T18:31:00Z"
resources:
- docs/scenario_guide/scenario_authoring.md
- docs/scenario_guide/curated_examples.md
- docs/scenario_guide/design_space_exploration.md
- docs/scenario_guide/empirical_database.md
---

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

## Core Guides

* **[Scenario Authoring](scenario_authoring.md)**: Documentation on the scenario `DraftState` pipeline and constraints.
* **[Curated Examples](curated_examples.md)**: An overview of the built-in, chemically balanced default scenarios.

## Work in Progress

* **[Evolutionary Encapsulated Multi-Stage Design Space Exploration (EEDSE)](design_space_exploration.md)**: Guide on utilizing the EEDSE Optimizer to discover stable ecological configurations.
* **[Empirical Database](empirical_database.md)**: Documentation on the underlying trait-pipeline that pulls from real-world scientific data.

---

## Future Prospects

* **[AI Coevolution & Distributed EEDSE Engine](../speculative_research/ai_coevolution_dse.md)**: Architecture for Ray/Tune + OptunaSearch distributed multi-objective Pareto optimization, AITL governance, and reinforcement learning swarm coevolution under EEDSE.
* **[Agentic Diagnostic Log Writer](../speculative_research/agentic_log_writer.md)**: Specification for the AITL diagnostic observer logging systemic integrity.
* **[Parameter Scaling & Calibration Strategy](../speculative_research/parameter_calibration_strategy.md)**: Exhaustive strategy for non-dimensionalizing and calibrating empirical traits to discrete simulation scales.

### 1. Scenario Authoring & Schema

Understand how to define your custom ecosystem configurations. This guide details:

* The Pydantic validation schema (`SimulationConfig`) ensuring configuration integrity before boot.
* The **Rule of 16** constraint, which limits flora, herbivores, and chemical substances to pre-allocated static cache lines, avoiding dynamic memory allocation latency during hot execution loops.
* How to define the **Diet Compatibility** and **Substance Trigger** matrices to construct complex trophic relationships.

### 2. Curated Examples

Inspect pre-configured blueprints designed to demonstrate specific ecological features:

* **The Eternal Canopy:** An complex, balanced forest biotope showing stabilized Lotka-Volterra wave propagation.
* **Trophic Collapse Scenario:** A demonstration of ecological breakdown when herbivore consumption rates breach flora regeneration thresholds.
* **Volatile Warning Cascade:** A scenario highlighting chemical atmospheric warning diffusion across spatial grids.

### 3. Evolutionary Encapsulated Multi-Stage Design Space Exploration (EEDSE)

Discover how the framework uses encapsulated parameter restriction and `pymoo` genetic algorithms to find stable parameters autonomously:

* **Optimization Search:** Why genetic/evolutionary search beats Random Walk and Simulated Annealing in rugged biological landscapes.
* **Cost Function Design:** How we penalize extinction events, reward survival time, and avoid "boring" stable states (e.g., $100\%$ flora, $0$ herbivores).

### 4. [Empirical Database Pipeline](empirical_database.md)

Explore the structural decoupling of archetypes, visual rule building, and our migration path toward true database persistence.
