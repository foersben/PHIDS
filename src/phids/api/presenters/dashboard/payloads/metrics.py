# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Plant metrics calculation for dashboard payloads."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from phids.api.presenters.dashboard.shared import calculate_structural_fragility_and_risk

if TYPE_CHECKING:
    from phids.engine.components.plant import PlantComponent


@dataclass(slots=True, frozen=True)
class PlantMetrics:
    """Biomass structural metrics and herbivory risk indicators for a single plant."""

    structural_mass: float
    max_structural_mass: float
    fragility_pct: float
    incidental_risk_level: str

    @property
    def risk_level(self) -> str:
        """Alias for incidental_risk_level for presenter compatibility."""
        return self.incidental_risk_level


def _compute_plant_metrics(p: PlantComponent) -> PlantMetrics:
    max_struct = p.max_structural_mass if p.max_structural_mass > 0.0 else p.max_energy
    struct_mass = p.structural_mass
    if struct_mass <= 0.0 and max_struct > 0.0:
        struct_mass = max_struct * min(1.0, max(0.0, p.energy / max_struct))
        p.structural_mass = struct_mass
        p.max_structural_mass = max_struct

    _fragility, fragility_pct, risk_level = calculate_structural_fragility_and_risk(struct_mass, max_struct)
    return PlantMetrics(
        structural_mass=struct_mass,
        max_structural_mass=max_struct,
        fragility_pct=fragility_pct,
        incidental_risk_level=risk_level,
    )
