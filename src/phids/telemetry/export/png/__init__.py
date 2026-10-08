# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Telemetry export to PNG images.

Renders publication-quality charts (time series, phase space, defense economy, biomass stacks,
and survival probability) using Matplotlib headless Agg backend to raw PNG bytes.
"""

from __future__ import annotations

from .core import generate_png_bytes

__all__ = ["generate_png_bytes"]
