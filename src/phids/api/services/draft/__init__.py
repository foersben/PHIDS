# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Draft-state mutation module for PHIDS scenario-builder workflows.

This package concentrates all imperative mutation procedures applied to the UI draft state into
pure, cohesive modules. These functions preserve the existing biological and algorithmic invariants
of the builder pipeline (species-id compaction, matrix resizing, trigger-tree pruning) while
maintaining a strictly data-oriented API decoupled from the request routing layer.
"""
