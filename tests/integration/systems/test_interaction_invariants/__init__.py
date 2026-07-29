# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Integration tests for deterministic interaction-phase arithmetic invariants.

This package decomposes the interaction-system's closed-form arithmetic verification
into focused modules, each targeting one metabolic sub-phase in isolation:

- ``test_attrition_invariants``: Parametric and monotonicity checks for
  per-tick metabolic energy drain and the ceiling-rule casualty calculation.
- ``test_reproduction_invariants``: Floor-based surplus-to-offspring conversion
  and monotone population growth invariants.
- ``test_mitosis_invariants``: Binary fission threshold semantics and population/
  energy conservation laws.

Shared setup helpers (``run_attrition_step``, ``run_reproduction_step``,
``run_mitosis_step``) live in ``conftest.py`` and are also consumed by
``test_interaction_hypothesis_pilot.py``, eliminating all duplication.
"""
