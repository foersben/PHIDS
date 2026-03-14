from __future__ import annotations

from phids.engine.core.biotope import GridEnvironment


def test_signal_diffusion_applies_threshold() -> None:
    env = GridEnvironment(width=6, height=6, num_signals=1, num_toxins=1)
    env.signal_layers[0, 2, 2] = 1e-6

    env.diffuse_signals()

    assert float(env.signal_layers[0].sum()) == 0.0


def test_signal_diffusion_wind_does_not_wrap_across_edges() -> None:
    env = GridEnvironment(width=6, height=6, num_signals=1, num_toxins=1)
    env.signal_layers[0, 5, 3] = 1.0
    env.set_uniform_wind(1.0, 0.0)

    env.diffuse_signals()

    assert float(env.signal_layers[0, 0, :].sum()) == 0.0

