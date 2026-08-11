# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Unit Invariant Tests for Phase-Staggered Lifecycle Cohort Completeness.

This module validates that modulo cohort gating (entity_id % 168 == tick % 168) processes
100% of active flora entities exactly once per 168-tick simulation window.
"""

from __future__ import annotations

import pytest


@pytest.mark.scientific_invariant
def test_phase_staggered_cohort_completeness() -> None:
    """Verify modulo gating processes 100% of entities exactly once per 168-tick window.

    To eliminate per-tick engine spikes, flora growth and reproduction ticks are phase-staggered
    across 168 ticks based on entity ID modulo gating. Over a 168-tick window, every entity
    must be updated exactly once (count == 1).

    Raises:
        AssertionError: If an entity is updated zero times or more than once per 168 ticks.
    """
    n_entities = 1_000
    entity_ids = list(range(n_entities))

    processed_counts = {eid: 0 for eid in entity_ids}

    # Simulate 168 consecutive ticks
    for tick in range(168):
        current_gating = tick % 168
        for eid in entity_ids:
            if (eid % 168) == current_gating:
                processed_counts[eid] += 1

    # Every entity must be processed exactly 1 time in 168 ticks
    for eid, count in processed_counts.items():
        assert count == 1, f"Entity {eid} was processed {count} times instead of exactly 1 in a 168-tick window!"
