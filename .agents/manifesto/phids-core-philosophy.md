---
type: manifesto
---
# PHIDS Core Philosophy

PHIDS (Plant-Herbivore Interaction & Defense Simulator) is developed in collaboration with the University of Jena. It is engineered to model complex ecological and biological behaviors within a highly deterministic environment.

1. **Science Over Shortcuts:** Mathematical correctness and deterministic replayability are non-negotiable. Do not sacrifice scientific accuracy for the sake of shipping a feature faster.
2. **Performance by Design:** Biological simulations scale exponentially. We rely on strict ECS data structures, double-buffering, and Numba JIT compilation to maintain high tick rates without degrading simulation fidelity.
3. **Transparency via Telemetry:** The engine's internal state must always be observable and serializable via our Zarr replay buffers. If an event alters the Biotope, it must be captured by the telemetry pipeline.
