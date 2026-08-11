# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Unit tests for PHIDS DraftState and UI state mutation invariants.

This package decomposes the ``test_ui_state`` module into focused sub-modules,
each covering one mutation domain of the ``DraftState`` singleton:

- ``test_condition_helpers``: SubstanceDefinition type labels, condition-path
  parsing, default condition node synthesis, tree navigation, pruning, and ID
  remapping.
- ``test_species_mutations``: Species removal, ID compaction, diet-matrix resizing,
  and trigger-rule remapping.
- ``test_biotope_and_substances``: Scalar biotope normalization, substance-registry
  compaction, diet-cell toggling, and Rule-of-16 enforcement.
- ``test_trigger_rule_mutators``: Trigger-rule tree CRUD operations and invalid-path
  error handling.
- ``test_placements_and_config``: Placement mutation, config building, and
  draft-singleton helper invariants.

All sub-modules share fixtures and builder helpers from ``conftest.py``.
"""
