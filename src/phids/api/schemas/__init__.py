# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Pydantic v2 schema package for the PHIDS API ingress boundary.

Submodules
----------
base
    ``StrictBaseModel`` and annotated species-id aliases (``SpeciesId``,
    ``HerbivoreId``, ``SubstanceId``).
ecs
    ECS component schemata for REST inspection endpoints.
conditions
    Recursive activation-condition predicate tree (``ConditionNode``).
triggers
    Trigger action schemas and the ``TriggerConditionSchema`` interaction-matrix entry.
species
    Per-species parameter schemas and ``DietCompatibilityMatrix``.
placement
    Initial placement and procedural placement strategy schemas.
simulation
    ``SimulationConfig`` - the authoritative engine construction container.
responses
    REST API response and request payload schemas.
"""
