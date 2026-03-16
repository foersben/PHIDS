"""Simulation systems sub-package executing per-tick ecological phase logic.

This sub-package implements the three ordered update phases that constitute each simulation tick
in the PHIDS engine. The lifecycle system (``run_lifecycle``) advances plant growth according to
species-specific rate parameters, evaluates reproduction candidates via probabilistic seed
dispersal, forms new mycorrhizal root connections between adjacent plants at configurable
intervals, and culls entities whose energy falls below the species survival threshold. The
interaction system (``run_interaction``) navigates herbivore swarms along the scalar flow-field
gradient using O(1) spatial hash co-occupancy lookups, applies diet-matrix-gated herbivory,
enforces metabolic attrition proportional to individual-level energy demands, and triggers mitosis
when swarm population exceeds the configured split threshold. The signaling system
(``run_signaling``) evaluates nested activation-condition trees against per-cell predator census
data, advances substance synthesis timers, emits volatile signals and defensive toxins into
environmental layers, relays signals through mycorrhizal networks, applies toxin-induced lethality
and repellency to co-located swarms, and delegates Gaussian diffusion to
``GridEnvironment.diffuse_signals``.

The systems are always invoked in the canonical order lifecycle → interaction → signaling to
preserve causal ordering: plant state is established before predators act, and chemical defenses
are resolved after herbivory has already been applied.
"""
