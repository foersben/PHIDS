"""Engine sub-package housing the deterministic PHIDS simulation runtime.

The engine package exposes the three architectural pillars of the PHIDS computational model.
The ``core`` sub-package provides the foundational data structures — the Entity-Component-System
registry, the double-buffered ``GridEnvironment`` biotope, and the Numba-accelerated flow-field
generator — upon which all higher-level simulation logic depends. The ``systems`` sub-package
implements the ordered set of per-tick update passes: lifecycle (plant growth, mycorrhizal
networking, reproduction, and culling), interaction (swarm movement via gradient navigation,
herbivory, metabolic attrition, and mitosis), and signaling (VOC synthesis, toxin emission,
Gaussian diffusion, and mycorrhizal signal relay). The ``components`` sub-package defines the
ECS dataclasses that carry per-entity runtime state across all three phases.

Together, these sub-packages implement the Rule-of-16-bounded, O(1) spatial-hash-indexed,
double-buffered simulation kernel described in the PHIDS architecture documentation.
"""
