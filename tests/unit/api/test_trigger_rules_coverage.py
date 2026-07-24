# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Coverage tests for trigger rules refactoring."""

from __future__ import annotations

from phids.api.routers.config.trigger_rules import _build_node_updates


def test_build_node_updates() -> None:
    """Test building node updates for different activation conditions."""
    # herbivore_presence
    res = _build_node_updates("herbivore_presence", herbivore_species_id=1, min_herbivore_population=5)
    assert res == {"herbivore_species_id": 1, "min_herbivore_population": 5}

    # substance_active
    res = _build_node_updates("substance_active", substance_id=2)
    assert res == {"substance_id": 2}

    # environmental_signal
    res = _build_node_updates("environmental_signal", signal_id=3, min_concentration=0.5)
    assert res == {"signal_id": 3, "min_concentration": 0.5}

    # all_of / any_of
    res = _build_node_updates("all_of", kind="any_of")
    assert res == {"kind": "any_of"}

    # default / miss
    res = _build_node_updates("unknown")
    assert res == {}
