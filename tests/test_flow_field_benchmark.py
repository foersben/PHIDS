from __future__ import annotations

import numpy as np

from phids.engine.core.flow_field import compute_flow_field


def test_flow_field_generation_benchmark(benchmark) -> None:  # type: ignore[no-untyped-def]
    width = 40
    height = 40
    plant_energy = np.zeros((width, height), dtype=np.float64)
    toxin_layers = np.zeros((4, width, height), dtype=np.float64)

    plant_energy[10, 10] = 10.0
    plant_energy[30, 20] = 4.0
    toxin_layers[0, 20, 20] = 2.0

    result = benchmark(compute_flow_field, plant_energy, toxin_layers, width, height)

    assert result.shape == (width, height)
    assert np.isfinite(result).all()
