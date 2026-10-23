import pytest
from unittest.mock import MagicMock
from phids.api.presenters.dashboard.cell_details.live import _collect_environmental_substances

def test_collect_environmental_substances_with_signal_and_toxin():
    plant = MagicMock()
    plant.x = 0
    plant.y = 0

    env = MagicMock()
    env.num_signals = 1
    env.num_toxins = 1

    # Define a mock signal_layers and toxin_layers
    # Let's mock a __getitem__ that returns a value > 0.0 for our mocked coords
    signal_layers = MagicMock()
    signal_layers.__getitem__.return_value = 1.0
    env.signal_layers = signal_layers

    toxin_layers = MagicMock()
    toxin_layers.__getitem__.return_value = 2.0
    env.toxin_layers = toxin_layers

    visible_substances = []
    visible_keys = set()
    substance_names = {0: "test_signal"}

    _collect_environmental_substances(plant, env, visible_substances, visible_keys, substance_names)

    assert len(visible_substances) == 2
    assert (0, False) in visible_keys
    assert (0, True) in visible_keys

def test_collect_environmental_substances_already_in_keys():
    plant = MagicMock()
    plant.x = 0
    plant.y = 0

    env = MagicMock()
    env.num_signals = 1
    env.num_toxins = 1

    signal_layers = MagicMock()
    signal_layers.__getitem__.return_value = 1.0
    env.signal_layers = signal_layers

    toxin_layers = MagicMock()
    toxin_layers.__getitem__.return_value = 2.0
    env.toxin_layers = toxin_layers

    visible_substances = []
    # Both already visible
    visible_keys = {(0, False), (0, True)}
    substance_names = {0: "test_signal"}

    _collect_environmental_substances(plant, env, visible_substances, visible_keys, substance_names)

    # Should not add them again
    assert len(visible_substances) == 0
