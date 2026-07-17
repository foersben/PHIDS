# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Matrices configuration routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, Response

import phids.api.main as api_main
from phids.api.services.draft.diet import set_diet_compatibility
from phids.api.ui_state import get_draft

router = APIRouter()


@router.post("/api/matrices/diet", response_class=HTMLResponse, summary="Toggle diet matrix cell")
async def matrix_diet(
    request: Request,
    herbivore_idx: Annotated[int, Form()],
    flora_idx: Annotated[int, Form()],
    compatible: Annotated[str, Form()] = "toggle",
) -> Response:
    """Toggle or set one diet compatibility cell in the draft matrix."""
    draft = get_draft()
    updated_value = set_diet_compatibility(
        draft,
        herbivore_idx,
        flora_idx,
        compatible,
    )
    if updated_value is not None:
        api_main.logger.debug(
            "Diet matrix updated (herbivore_idx=%d, flora_idx=%d, compatible=%s)",
            herbivore_idx,
            flora_idx,
            updated_value,
        )
    else:
        api_main.logger.warning(
            "Diet matrix update ignored for out-of-range indices (herbivore_idx=%d, flora_idx=%d)",
            herbivore_idx,
            flora_idx,
        )
    return api_main.templates.TemplateResponse(
        request,
        "partials/diet_matrix.html",
        {
            "flora_species": draft.flora_species,
            "herbivore_species": draft.herbivore_species,
            "diet_matrix": draft.diet_matrix,
        },
    )
