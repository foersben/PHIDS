# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Integration checks for simulation-control and scenario HTTP routes.

Decomposed into:
- ``test_simulation_control_routes``: Root controls, simulation status, start/pause/step/reset,
  wind/tick rate updates, telemetry exports, middleware logs.
- ``test_scenario_routes``: Scenario import/export, trigger materialization, load-draft task cancellation.
"""
