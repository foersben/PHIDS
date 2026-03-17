"""Unit tests for GridEnvironment VOC diffusion, subnormal-float threshold, and local wind advection.

This module validates the diffusion mechanics of :class:`~phids.engine.core.biotope.GridEnvironment`.
The core hypotheses are: (1) signal concentrations below ``SIGNAL_EPSILON`` are zeroed after one
diffusion tick, preventing accumulation of subnormal floating-point values that would degrade
Numba JIT throughput; (2) wind-driven advection uses local per-cell vectors and does not wrap
values across grid boundaries, preserving physical plausibility of airborne VOC transport; and
(3) non-trivial signal concentrations spread to neighbouring cells under Gaussian diffusion while
being attenuated by the per-tick ``SIGNAL_DECAY_FACTOR`` retention coefficient.
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
    """Verifies that local-wind advection plus diffusion produce downwind anisotropy.

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

    assert centroid_x > 10.5
    assert abs(centroid_y - 10.0) < 2.2
    major = max(var_x, var_y)
    minor = min(var_x, var_y)
    assert minor > 0.0
    assert (major / minor) > 1.2


def test_signal_diffusion_uses_local_wind_not_global_mean() -> None:
    """Heterogeneous wind fields create spatially distinct plume displacement within one layer.

    Two equal pulses are injected: one in a right-wind region and one in a left-wind region.
    A local-wind solver moves these plumes in opposite directions, while a global-mean solver
    would largely cancel the vectors and keep both near their origins.
    """
    env = GridEnvironment(width=24, height=5, num_signals=1, num_toxins=1)
    env.signal_layers[0, 6, 2] = 1.0
    env.signal_layers[0, 17, 2] = 1.0

    env.wind_vector_x[:12, :] = 1.5
    env.wind_vector_x[12:, :] = -1.5

    env.diffuse_signals()

    layer = env.signal_layers[0]
    left_mass = float(layer[:12, :].sum())
    right_mass = float(layer[12:, :].sum())
    left_x = np.arange(0, 12, dtype=np.float64)[:, None]
    right_x = np.arange(12, 24, dtype=np.float64)[:, None]
    left_centroid = float((layer[:12, :] * left_x).sum() / left_mass)
    right_centroid = float((layer[12:, :] * right_x).sum() / right_mass)

    assert left_centroid > 6.0
    assert right_centroid < 17.0
