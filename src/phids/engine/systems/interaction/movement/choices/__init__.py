# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Flow-field directional choice logic.

Provides JIT-compiled kernels and Python fallbacks for making weighted movement choices along
environmental flow fields, including branchless capacity mask integration.
"""

from __future__ import annotations

from .jit import (
    _adjust_scores_and_find_extrema_jit,
    _choose_neighbour_by_flow_probability_jit,
    _flat_field_choice_jit,
    _softmax_field_choice_jit,
    _weighted_field_choice_jit,
)
from .python import (
    _choose_neighbour_by_flow_probability,
    _choose_neighbour_by_flow_probability_python,
    _python_flat_field_choice,
    _python_weighted_field_choice,
)

__all__ = [
    "_adjust_scores_and_find_extrema_jit",
    "_choose_neighbour_by_flow_probability",
    "_choose_neighbour_by_flow_probability_jit",
    "_choose_neighbour_by_flow_probability_python",
    "_flat_field_choice_jit",
    "_python_flat_field_choice",
    "_python_weighted_field_choice",
    "_softmax_field_choice_jit",
    "_weighted_field_choice_jit",
]
