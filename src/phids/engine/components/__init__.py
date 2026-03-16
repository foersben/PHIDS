"""ECS component dataclasses for the PHIDS simulation engine.

This sub-package provides the three canonical ECS component types used throughout the PHIDS
engine. ``PlantComponent`` carries per-entity runtime state for flora entities, including energy
reserves, spatial coordinates, species identity, reproduction timers, camouflage parameters, and
mycorrhizal network membership. ``SwarmComponent`` carries per-entity runtime state for herbivore
swarm entities, including population count, energy, velocity parameters, movement inertia, and
chemical-repellency flags. ``SubstanceComponent`` carries the synthesis and activation state for
volatile organic compound (VOC) signals and defensive toxins emitted by plant entities in response
to herbivore pressure.

All three dataclasses use ``slots=True`` to minimise per-instance memory overhead. Their fields
hold only primitive-typed values, obeying the data-oriented design principle that prohibits object
graph nesting within ECS components. Per-tick mutations in the lifecycle, interaction, and
signaling systems operate directly on these fields without allocating new Python objects, satisfying
the Rule-of-16 pre-allocation invariant.
"""
