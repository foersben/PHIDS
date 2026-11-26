# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Engine sub-package housing the deterministic PHIDS simulation runtime.

Why: Decoupling the ecological simulation kernel from web, CLI, and analytics adapters allows deterministic tick trajectories to execute identically across interactive WebSocket sessions, headless Monte Carlo ensembles, and scientific invariant tests.

How: The package organises state and behaviour into four orthogonal layers - ``core`` (contiguous double-buffered arrays, Entity-Component-System registries, and Numba solvers), ``components`` (Rule-of-16-aligned ECS dataclasses), ``systems`` (pure per-tick passes for lifecycle, interaction, and signalling), and ``batch`` (spawned multiprocess ensemble orchestration).
"""
