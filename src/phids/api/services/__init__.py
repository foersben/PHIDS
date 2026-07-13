# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Service-layer package for deterministic API-side state mutation.

This package contains imperative orchestration services that mutate validated, server-owned
state containers used by the PHIDS API surface. The separation isolates mutation workflows from
state representation, enabling route handlers to invoke explicit service operations while keeping
dataclasses focused on structural data and schema transformation responsibilities.
"""

from phids.api.services.draft_service import DraftService

__all__ = ["DraftService"]
