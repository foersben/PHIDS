# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""DSE validation endpoints.

Contains routes to validate pre-flight invariants for Design Space Exploration (DSE) candidates.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/dse", tags=["DSE Validation"])
