"""Core engine sub-package: ECS world, biotope environment, and flow-field kernel.

This sub-package contains the three lowest-level, performance-critical modules of the PHIDS
engine. The :mod:`~phids.engine.core.ecs` module implements the flat Entity-Component-System
registry and O(1) spatial hash grid that enable efficient co-locality queries without O(N²)
distance scans. The :mod:`~phids.engine.core.biotope` module implements the double-buffered
``GridEnvironment``, which maintains pre-allocated NumPy arrays for plant energy, airborne signal,
and toxin layers and performs Gaussian diffusion via 2-D convolution each tick. The
:mod:`~phids.engine.core.flow_field` module implements the iterative Jacobi propagation kernel,
JIT-compiled with Numba for hot-path performance, that converts aggregated plant energy and toxin
concentrations into the scalar attraction field driving swarm navigation.

All three modules observe the Rule-of-16 memory allocation discipline and the ``SIGNAL_EPSILON``
threshold invariant for subnormal-float suppression.
"""
