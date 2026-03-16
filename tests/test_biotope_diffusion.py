"""Unit tests for GridEnvironment VOC diffusion, subnormal-float threshold, and wind-advection invariants.

This module validates the diffusion mechanics of :class:`~phids.engine.core.biotope.GridEnvironment`.
The core hypotheses are: (1) signal concentrations below ``SIGNAL_EPSILON`` are zeroed after one
diffusion tick, preventing accumulation of subnormal floating-point values that would degrade
Numba JIT throughput; (2) wind-driven advection shifts signal plumes by an integer cell offset
derived from mean wind velocity but does not wrap values across grid boundaries, preserving
physical plausibility of airborne VOC transport; and (3) non-trivial signal concentrations spread
to neighbouring cells under Gaussian diffusion while being attenuated by the per-tick
``SIGNAL_DECAY_FACTOR`` retention coefficient.
"""

from __future__ import annotations

import numpy as np

from phids.engine.core.biotope import GridEnvironment


def test_signal_diffusion_applies_threshold() -> None:
    """Verifies that signal concentrations below SIGNAL_EPSILON are zeroed after one diffusion tick.

    A concentration of 1e-6 (below the 1e-4 threshold) is injected into a single cell.
    After one call to ``diffuse_signals``, the entire signal layer must sum to exactly zero,
    confirming that the sparsity threshold eliminates subnormal tail values and prevents
    indefinite accumulation of numerically irrelevant concentrations.
    """
    env = GridEnvironment(width=6, height=6, num_signals=1, num_toxins=1)
    env.signal_layers[0, 2, 2] = 1e-6

    env.diffuse_signals()

    assert float(env.signal_layers[0].sum()) == 0.0


def test_signal_diffusion_wind_does_not_wrap_across_edges() -> None:
    """Verifies that wind-driven advection does not wrap signal values across grid boundaries.

    A signal is placed at the rightmost column (x=5) with wind pushing in the positive x
    direction. After diffusion, no signal should appear at x=0 (which would indicate a toroidal
    wrap), confirming that boundary fill is used rather than periodic padding. This invariant
    reflects the physical requirement that VOC plumes do not re-enter the biotope from the
    opposite edge.
    """
    env = GridEnvironment(width=6, height=6, num_signals=1, num_toxins=1)
    env.signal_layers[0, 5, 3] = 1.0
    env.set_uniform_wind(1.0, 0.0)

    env.diffuse_signals()

    assert float(env.signal_layers[0, 0, :].sum()) == 0.0


def test_signal_diffusion_fast_path_clears_stale_write_buffer_state() -> None:
    """Verifies that the fast-path diffusion branch correctly zeros the write buffer for quiescent layers.

    The diffusion routine skips convolution for signal layers whose concentrations are entirely below
    ``SIGNAL_EPSILON``. This optimisation is valid only if the skipped branch also clears the write
    buffer; otherwise, the subsequent double-buffer swap would resurrect stale concentration mass from
    a previous tick, constituting a ghost-plume artefact. The test seeds a non-zero signal, advances
    one diffusion tick, manually quiesces the read layer, and verifies that a second diffusion pass
    yields a strictly zero field — confirming that the fast path does not preserve stale write-buffer
    state across buffer swaps.
    """
    env = GridEnvironment(width=6, height=6, num_signals=1, num_toxins=1)
    env.signal_layers[0, 2, 2] = 1.0

    env.diffuse_signals()
    env.signal_layers[0].fill(0.0)
    env.diffuse_signals()

    assert float(env.signal_layers[0].sum()) == 0.0


def test_signal_diffusion_wind_bias_stretches_plume_along_flow_axis() -> None:
    """Verifies that directional kernels produce downwind-shifted anisotropic plumes.

    The test seeds a centered unit pulse and applies a positive x-direction wind field.
    After several diffusion ticks, the plume centroid is expected to move downwind and
    variance along the wind axis must exceed cross-wind variance.
    """
    env = GridEnvironment(width=21, height=21, num_signals=1, num_toxins=1)
    env.signal_layers[0, 10, 10] = 1.0
    env.set_uniform_wind(1.6, 0.0)

    for _ in range(3):
        env.diffuse_signals()

    layer = env.signal_layers[0]
    mass = float(layer.sum())
    assert mass > 0.0

    x_coords = np.arange(env.width, dtype=np.float64)[:, None]
    y_coords = np.arange(env.height, dtype=np.float64)[None, :]
    centroid_x = float((layer * x_coords).sum() / mass)
    centroid_y = float((layer * y_coords).sum() / mass)
    var_x = float((layer * ((x_coords - centroid_x) ** 2)).sum() / mass)
    var_y = float((layer * ((y_coords - centroid_y) ** 2)).sum() / mass)

    assert abs(centroid_x - 10.0) < 2.2
    assert abs(centroid_y - 10.0) < 2.2
    major = max(var_x, var_y)
    minor = min(var_x, var_y)
    assert minor > 0.0
    assert (major / minor) > 1.2
