# Scientific Model

This section formally details the Plant-Herbivore Interaction & Defense Simulator (PHIDS) as a rigorous, deterministic computational ecology model. The documentation here defines the theoretical foundations, the explicit mathematical representations of the biological mechanisms, and the bounded approximations underlying the execution of the system.

PHIDS operates as a coupled hybrid dynamical system. Discrete entity transitions within a data-oriented Entity-Component-System (ECS) are strictly synchronized with continuous field updates executing across double-buffered cellular automata layers. This section will guide you through the algorithmic translation of complex phenomena—resource acquisition, predation pressure, induced signaling, metabolic attrition, and swarm dispersal—into transparent, causal operator chains.

## Core Chapters

- **[Mathematical Framework](mathematical_framework.md)**: A comprehensive, equation-driven exposition of the model. It elucidates the bounded ecological abstractions, details the deterministic phase sequence, and presents the formal update laws governing the biotope, flora lifecycle, swarm interaction, and the signaling pathways.

By prioritizing formal exposition, explicit boundaries, and the rationale behind each numerical approximation, this section ensures that the output telemetry from PHIDS is mathematically traceable and experimentally reproducible.

## Merged Legacy Concepts

To preserve the historical intent of the model, the following legacy documents were consolidated into the `mathematical_framework.md`:
- `foundations/research-scope.md`
- `engine/formal-algorithmic-model.md`
- `engine/flow-field.md`
- `engine/signaling.md`
- `engine/interaction.md`
- `engine/lifecycle.md`

We have retained the core mathematical formulas and explanations surrounding the Reaction-Diffusion systems, Chemotactic movement, and the discrete Time Step integrations, enhancing them to explain *why* these models were chosen over standard OOP or continuous-time methodologies.
