# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Types for PNG export."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from phids.telemetry.analytics import TelemetryRow

TelemetryRows = list["TelemetryRow"]
