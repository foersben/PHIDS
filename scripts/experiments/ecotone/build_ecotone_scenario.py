# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Build and validate the Central European Riparian-to-Floodplain-Meadow Ecotone scenarios.

Constructs deterministic (seed = 42) SimulationConfig payloads for both the
256 x 256 flagship production biotope and its 128 x 64 bit-exact interactive twin,
reconciling the v1.1 ecotone report specifications with PHIDS v0.10.0 schemas.

Engine configuration note:
    ``GridEnvironment.swarm_populations`` is dimensioned by ``MAX_HERBIVORE_SPECIES``,
    so setting ``num_signals = 3`` and ``num_toxins = 9`` (total 12 <= 16 Rule-of-16
    cap) supports all five herbivore guilds cleanly without unused signal channels.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from phids.api.schemas.conditions import (
    AllOfConditionSchema,
    AnyOfConditionSchema,
    ConditionNode,
    EnvironmentalSignalConditionSchema,
    HerbivorePresenceConditionSchema,
    SubstanceActiveConditionSchema,
)
from phids.api.schemas.placement import InitialPlantPlacement, InitialSwarmPlacement
from phids.api.schemas.simulation import SimulationConfig
from phids.api.schemas.species import (
    DietCompatibilityMatrix,
    FloraSpeciesParams,
    HerbivoreResistancesSchema,
    HerbivoreSpeciesParams,
)
from phids.api.schemas.triggers import (
    EnvironmentalSignalInitiator,
    HerbivoreAttackInitiator,
    PassiveDefensesSchema,
    ResourceWithdrawalAction,
    SynthesizeSubstanceAction,
    TriggerConditionSchema,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
OUTPUT_DIR = REPO_ROOT / "examples" / "scenarios"

SUBSTANCE_NAMES: dict[int, str] = {
    0: "(Z)-3-Hexenyl Acetate (GLV)",
    1: "(E)-beta-Ocimene / DMNT",
    2: "MeSA + CMN Jasmonate",
    3: "Benzyl Cyanide (Repellent)",
    4: "Kunitz TI / Salicinoids (Lethal)",
    5: "beta-Thujone / Camphor (Repellent)",
    6: "Trifolium HCN (Lethal)",
    7: "Allyl Isothiocyanate (Lethal)",
    8: "Lolium PPO + Silica (Lethal)",
}


def _env_sig(
    signal_id: int, half_saturation: float, hill_n: float, min_conc: float = 0.01
) -> EnvironmentalSignalInitiator:
    return EnvironmentalSignalInitiator(
        signal_id=signal_id,
        min_concentration=min_conc,
        response_curve="hill",
        hill_cooperativity=hill_n,
        half_saturation=half_saturation,
    )


def _herb_atk(herbivore_id: int, min_pop: int) -> HerbivoreAttackInitiator:
    return HerbivoreAttackInitiator(
        herbivore_species_id=herbivore_id,
        min_herbivore_population=min_pop,
    )


def _synth_signal(sub_id: int, synth_dur: int, cost: float) -> SynthesizeSubstanceAction:
    return SynthesizeSubstanceAction(
        substance_id=sub_id,
        synthesis_duration=synth_dur,
        is_toxin=False,
        lethal=False,
        lethality_rate=0.0,
        repellent=False,
        repellent_walk_ticks=0,
        energy_cost_per_tick=cost,
        irreversible=False,
    )


def _synth_toxin(
    sub_id: int,
    synth_dur: int,
    cost: float,
    *,
    lethal: bool = False,
    lethality_rate: float = 0.0,
    repellent: bool = False,
    repellent_walk_ticks: int = 0,
) -> SynthesizeSubstanceAction:
    return SynthesizeSubstanceAction(
        substance_id=sub_id,
        synthesis_duration=synth_dur,
        is_toxin=True,
        lethal=lethal,
        lethality_rate=lethality_rate,
        repellent=repellent,
        repellent_walk_ticks=repellent_walk_ticks,
        energy_cost_per_tick=cost,
        irreversible=False,
    )


def _sig_active(substance_id: int) -> SubstanceActiveConditionSchema:
    return SubstanceActiveConditionSchema(substance_id=substance_id)


def _env_cond(signal_id: int, min_concentration: float) -> EnvironmentalSignalConditionSchema:
    return EnvironmentalSignalConditionSchema(signal_id=signal_id, min_concentration=min_concentration)


def _herb_cond(herbivore_species_id: int, min_herbivore_population: int) -> HerbivorePresenceConditionSchema:
    return HerbivorePresenceConditionSchema(
        herbivore_species_id=herbivore_species_id,
        min_herbivore_population=min_herbivore_population,
    )


def _all_of(*conditions: ConditionNode) -> AllOfConditionSchema:
    return AllOfConditionSchema(conditions=list(conditions))


def _any_of(*conditions: ConditionNode) -> AnyOfConditionSchema:
    return AnyOfConditionSchema(conditions=list(conditions))


def build_flora_species() -> list[FloraSpeciesParams]:
    """Return the six validated European riparian-meadow flora species."""
    # Stage-1 attack -> alarm signal triggers are unconditional; Stage-2 relays
    # and resource withdrawal require Stage-1 signalling; Stage-3 toxins use
    # multi-stage priming and escalating presence/signal gates.
    p0_triggers = [
        TriggerConditionSchema(
            initiator=_herb_atk(0, 4),
            aftereffect_ticks=6,
            activation_condition=None,
            action=_synth_signal(0, 1, 0.03),
        ),
        TriggerConditionSchema(
            initiator=_herb_atk(1, 4),
            aftereffect_ticks=6,
            activation_condition=None,
            action=_synth_signal(0, 1, 0.03),
        ),
        TriggerConditionSchema(
            initiator=_herb_atk(0, 4),
            aftereffect_ticks=12,
            activation_condition=None,
            action=_synth_signal(2, 3, 0.05),
        ),
        TriggerConditionSchema(
            initiator=_herb_atk(0, 4),
            aftereffect_ticks=12,
            activation_condition=_sig_active(0),
            action=ResourceWithdrawalAction(apparent_nutrition_factor=0.45, withdrawal_duration=24),
        ),
        TriggerConditionSchema(
            initiator=_env_sig(0, 0.133, 3.0),
            aftereffect_ticks=8,
            activation_condition=_env_cond(0, 0.05),
            action=_synth_signal(1, 1, 0.05),
        ),
        TriggerConditionSchema(
            initiator=_env_sig(0, 0.133, 3.0),
            aftereffect_ticks=14,
            activation_condition=_any_of(_herb_cond(0, 2), _env_cond(1, 0.04)),
            action=_synth_toxin(3, 2, 0.11, repellent=True, repellent_walk_ticks=5),
        ),
        TriggerConditionSchema(
            initiator=_env_sig(1, 0.093, 3.0),
            aftereffect_ticks=18,
            activation_condition=_any_of(_herb_cond(0, 2), _sig_active(3)),
            action=_synth_toxin(4, 2, 0.16, lethal=True, lethality_rate=0.062493),
        ),
        TriggerConditionSchema(
            initiator=_herb_atk(0, 4),
            aftereffect_ticks=14,
            activation_condition=_sig_active(0),
            action=_synth_toxin(3, 12, 0.11, repellent=True, repellent_walk_ticks=5),
        ),
        TriggerConditionSchema(
            initiator=_herb_atk(0, 4),
            aftereffect_ticks=18,
            activation_condition=_all_of(_sig_active(0), _sig_active(3)),
            action=_synth_toxin(4, 12, 0.16, lethal=True, lethality_rate=0.062493),
        ),
    ]

    p1_triggers = [
        TriggerConditionSchema(
            initiator=_herb_atk(1, 4),
            aftereffect_ticks=6,
            activation_condition=None,
            action=_synth_signal(0, 1, 0.03),
        ),
        TriggerConditionSchema(
            initiator=_herb_atk(1, 4),
            aftereffect_ticks=12,
            activation_condition=None,
            action=_synth_signal(2, 3, 0.05),
        ),
        TriggerConditionSchema(
            initiator=_herb_atk(1, 4),
            aftereffect_ticks=12,
            activation_condition=_sig_active(0),
            action=ResourceWithdrawalAction(apparent_nutrition_factor=0.70, withdrawal_duration=24),
        ),
        TriggerConditionSchema(
            initiator=_env_sig(0, 0.133, 3.0),
            aftereffect_ticks=8,
            activation_condition=_env_cond(0, 0.05),
            action=_synth_signal(1, 1, 0.05),
        ),
        TriggerConditionSchema(
            initiator=_env_sig(2, 0.109, 2.0),
            aftereffect_ticks=18,
            activation_condition=_any_of(_herb_cond(1, 2), _env_cond(0, 0.04)),
            action=_synth_toxin(4, 2, 0.16, lethal=True, lethality_rate=0.054682),
        ),
        TriggerConditionSchema(
            initiator=_herb_atk(1, 4),
            aftereffect_ticks=18,
            activation_condition=_any_of(_sig_active(0), _sig_active(2)),
            action=_synth_toxin(4, 12, 0.16, lethal=True, lethality_rate=0.054682),
        ),
    ]

    p2_triggers = [
        TriggerConditionSchema(
            initiator=_herb_atk(2, 6),
            aftereffect_ticks=12,
            activation_condition=None,
            action=_synth_signal(2, 3, 0.05),
        ),
        TriggerConditionSchema(
            initiator=_herb_atk(3, 4),
            aftereffect_ticks=12,
            activation_condition=None,
            action=_synth_signal(2, 3, 0.05),
        ),
        TriggerConditionSchema(
            initiator=_herb_atk(2, 6),
            aftereffect_ticks=12,
            activation_condition=_sig_active(2),
            action=ResourceWithdrawalAction(apparent_nutrition_factor=0.55, withdrawal_duration=24),
        ),
        TriggerConditionSchema(
            initiator=_env_sig(2, 0.109, 2.0),
            aftereffect_ticks=12,
            activation_condition=_herb_cond(3, 2),
            action=_synth_toxin(
                6, 1, 0.13, lethal=True, lethality_rate=0.083917, repellent=True, repellent_walk_ticks=5
            ),
        ),
        TriggerConditionSchema(
            initiator=_herb_atk(3, 4),
            aftereffect_ticks=12,
            activation_condition=_sig_active(2),
            action=_synth_toxin(
                6, 8, 0.13, lethal=True, lethality_rate=0.083917, repellent=True, repellent_walk_ticks=5
            ),
        ),
    ]

    p3_triggers = [
        TriggerConditionSchema(
            initiator=_env_sig(2, 0.109, 2.0),
            aftereffect_ticks=16,
            activation_condition=_herb_cond(3, 2),
            action=_synth_toxin(8, 2, 0.12, lethal=True, lethality_rate=0.092309),
        ),
        TriggerConditionSchema(
            initiator=_herb_atk(3, 4),
            aftereffect_ticks=16,
            activation_condition=_sig_active(2),
            action=_synth_toxin(8, 10, 0.12, lethal=True, lethality_rate=0.092309),
        ),
        TriggerConditionSchema(
            initiator=_herb_atk(3, 4),
            aftereffect_ticks=12,
            activation_condition=None,
            action=_synth_signal(2, 3, 0.05),
        ),
    ]

    p4_triggers = [
        TriggerConditionSchema(
            initiator=_env_sig(0, 0.133, 3.0),
            aftereffect_ticks=16,
            activation_condition=_env_cond(0, 0.04),
            action=_synth_toxin(5, 1, 0.10, repellent=True, repellent_walk_ticks=8),
        ),
        TriggerConditionSchema(
            initiator=_env_sig(2, 0.109, 2.0),
            aftereffect_ticks=16,
            activation_condition=_any_of(_herb_cond(3, 2), _env_cond(0, 0.03)),
            action=_synth_toxin(5, 1, 0.10, repellent=True, repellent_walk_ticks=8),
        ),
        TriggerConditionSchema(
            initiator=_herb_atk(3, 3),
            aftereffect_ticks=16,
            activation_condition=_sig_active(0),
            action=_synth_toxin(5, 3, 0.10, repellent=True, repellent_walk_ticks=8),
        ),
        TriggerConditionSchema(
            initiator=_herb_atk(3, 3),
            aftereffect_ticks=6,
            activation_condition=None,
            action=_synth_signal(0, 1, 0.03),
        ),
    ]

    p5_triggers = [
        TriggerConditionSchema(
            initiator=_herb_atk(4, 4),
            aftereffect_ticks=6,
            activation_condition=None,
            action=_synth_signal(0, 1, 0.03),
        ),
        TriggerConditionSchema(
            initiator=_herb_atk(3, 4),
            aftereffect_ticks=6,
            activation_condition=None,
            action=_synth_signal(0, 1, 0.03),
        ),
        TriggerConditionSchema(
            initiator=_env_sig(0, 0.133, 3.0),
            aftereffect_ticks=16,
            activation_condition=_herb_cond(3, 2),
            action=_synth_toxin(7, 2, 0.17, lethal=True, lethality_rate=0.067134),
        ),
        TriggerConditionSchema(
            initiator=_herb_atk(3, 4),
            aftereffect_ticks=16,
            activation_condition=_all_of(_sig_active(0), _herb_cond(3, 4)),
            action=_synth_toxin(7, 8, 0.17, lethal=True, lethality_rate=0.067134),
        ),
    ]

    return [
        FloraSpeciesParams(
            species_id=0,
            name="Populus nigra",
            base_energy=70.0,
            max_energy=140.0,
            growth_rate=0.1500,
            survival_threshold=14.0,
            reproduction_interval=1303,
            seed_min_dist=6.0,
            seed_max_dist=28.0,
            seed_energy_cost=56.0,
            camouflage=False,
            camouflage_factor=1.0,
            translocation_rate=0.08,
            mycorrhizal_tax_per_link=0.65,
            passive_defenses=PassiveDefensesSchema(mechanical_damage_per_bite=0.05, digestibility_modifier=0.88),
            triggers=p0_triggers,
            structural_mass_max=140.0,
            structural_growth_rate=0.008,
        ),
        FloraSpeciesParams(
            species_id=1,
            name="Salix purpurea",
            base_energy=60.0,
            max_energy=120.0,
            growth_rate=0.093509,
            survival_threshold=12.0,
            reproduction_interval=1737,
            seed_min_dist=5.0,
            seed_max_dist=22.0,
            seed_energy_cost=48.0,
            camouflage=False,
            camouflage_factor=1.0,
            translocation_rate=0.05,
            mycorrhizal_tax_per_link=0.55,
            passive_defenses=PassiveDefensesSchema(mechanical_damage_per_bite=0.15, digestibility_modifier=0.62),
            triggers=p1_triggers,
            structural_mass_max=120.0,
            structural_growth_rate=0.010,
        ),
        FloraSpeciesParams(
            species_id=2,
            name="Trifolium repens",
            base_energy=45.0,
            max_energy=85.0,
            growth_rate=0.3000,
            survival_threshold=9.0,
            reproduction_interval=1086,
            seed_min_dist=1.0,
            seed_max_dist=5.0,
            seed_energy_cost=34.1549,
            camouflage=False,
            camouflage_factor=1.0,
            translocation_rate=0.10,
            mycorrhizal_tax_per_link=0.50,
            passive_defenses=PassiveDefensesSchema(mechanical_damage_per_bite=0.0, digestibility_modifier=0.96),
            triggers=p2_triggers,
            structural_mass_max=85.0,
            structural_growth_rate=0.006,
        ),
        FloraSpeciesParams(
            species_id=3,
            name="Lolium perenne",
            base_energy=55.0,
            max_energy=105.0,
            growth_rate=0.3200,
            survival_threshold=11.0,
            reproduction_interval=1086,
            seed_min_dist=1.0,
            seed_max_dist=8.0,
            seed_energy_cost=42.6936,
            camouflage=False,
            camouflage_factor=1.0,
            translocation_rate=0.06,
            mycorrhizal_tax_per_link=0.50,
            passive_defenses=PassiveDefensesSchema(mechanical_damage_per_bite=0.22, digestibility_modifier=0.68),
            triggers=p3_triggers,
            structural_mass_max=105.0,
            structural_growth_rate=0.008,
        ),
        FloraSpeciesParams(
            species_id=4,
            name="Tanacetum vulgare",
            base_energy=50.0,
            max_energy=100.0,
            growth_rate=0.1800,
            survival_threshold=10.0,
            reproduction_interval=1737,
            seed_min_dist=1.0,
            seed_max_dist=6.0,
            seed_energy_cost=40.0,
            camouflage=True,
            camouflage_factor=0.35,
            translocation_rate=0.05,
            mycorrhizal_tax_per_link=0.35,
            passive_defenses=PassiveDefensesSchema(mechanical_damage_per_bite=0.04, digestibility_modifier=0.86),
            triggers=p4_triggers,
            structural_mass_max=100.0,
            structural_growth_rate=0.007,
        ),
        FloraSpeciesParams(
            species_id=5,
            name="Brassica nigra",
            base_energy=35.0,
            max_energy=68.0,
            growth_rate=0.5200,
            survival_threshold=7.0,
            reproduction_interval=868,
            seed_min_dist=1.0,
            seed_max_dist=4.0,
            seed_energy_cost=24.3964,
            camouflage=False,
            camouflage_factor=1.0,
            translocation_rate=0.05,
            mycorrhizal_tax_per_link=0.0,
            passive_defenses=PassiveDefensesSchema(mechanical_damage_per_bite=0.0, digestibility_modifier=0.97),
            triggers=p5_triggers,
            structural_mass_max=68.0,
            structural_growth_rate=0.005,
        ),
    ]


def build_herbivore_species() -> list[HerbivoreSpeciesParams]:
    """Return the five diurnal-stride-calibrated European herbivore guilds."""
    # Foraging and metabolic parameters calibrated to PHIDS runtime units where
    # feeding executes on 24-tick diurnal strides alongside hourly basal upkeep.
    return [
        HerbivoreSpeciesParams(
            species_id=0,
            name="Lymantria dispar",
            energy_min=1.40,
            velocity=2,
            consumption_rate=3.3337,
            handling_time=0.113987,
            behavior_paradigm="macro_swarm",
            softmax_temperature=0.22,
            reproduction_energy_divisor=2.1,
            energy_upkeep_per_individual=0.00843,
            resistances=HerbivoreResistancesSchema(
                morphological_adaptation=0.10, chemical_neutralization=0.05, digestive_efficiency=0.38
            ),
            split_population_threshold=26,
            evasion_duration_ticks=5,
        ),
        HerbivoreSpeciesParams(
            species_id=1,
            name="Phratora vitellinae",
            energy_min=1.00,
            velocity=2,
            consumption_rate=2.352273,
            handling_time=0.172599,
            behavior_paradigm="macro_swarm",
            softmax_temperature=0.20,
            reproduction_energy_divisor=2.5,
            energy_upkeep_per_individual=0.009907,
            resistances=HerbivoreResistancesSchema(
                morphological_adaptation=0.35, chemical_neutralization=0.20, digestive_efficiency=0.42
            ),
            split_population_threshold=24,
            evasion_duration_ticks=5,
        ),
        HerbivoreSpeciesParams(
            species_id=2,
            name="Acyrthosiphon pisum",
            energy_min=1.10,
            velocity=1,
            consumption_rate=2.666371,
            handling_time=0.126764,
            behavior_paradigm="macro_swarm",
            softmax_temperature=0.16,
            reproduction_energy_divisor=2.0,
            energy_upkeep_per_individual=0.012152,
            resistances=HerbivoreResistancesSchema(
                morphological_adaptation=0.15, chemical_neutralization=0.05, digestive_efficiency=0.65
            ),
            split_population_threshold=46,
            evasion_duration_ticks=4,
        ),
        HerbivoreSpeciesParams(
            species_id=3,
            name="Noctua pronuba",
            energy_min=1.10,
            velocity=3,
            consumption_rate=1.513921,
            handling_time=0.334232,
            behavior_paradigm="macro_swarm",
            softmax_temperature=0.24,
            reproduction_energy_divisor=2.4,
            energy_upkeep_per_individual=0.010547,
            resistances=HerbivoreResistancesSchema(
                morphological_adaptation=0.15, chemical_neutralization=0.10, digestive_efficiency=0.48
            ),
            split_population_threshold=26,
            evasion_duration_ticks=5,
        ),
        HerbivoreSpeciesParams(
            species_id=4,
            name="Pieris brassicae",
            energy_min=1.00,
            velocity=2,
            consumption_rate=2.706364,
            handling_time=0.163319,
            behavior_paradigm="macro_swarm",
            softmax_temperature=0.15,
            reproduction_energy_divisor=2.4,
            energy_upkeep_per_individual=0.009814,
            resistances=HerbivoreResistancesSchema(
                morphological_adaptation=0.20, chemical_neutralization=0.15, digestive_efficiency=0.44
            ),
            split_population_threshold=24,
            evasion_duration_ticks=5,
        ),
    ]


def _has_cardinal_neighbor(occupied: np.ndarray, x: int, y: int, width: int, height: int) -> bool:
    return bool(
        occupied[(x - 1) % width, y] >= 0
        or occupied[(x + 1) % width, y] >= 0
        or occupied[x, (y - 1) % height] >= 0
        or occupied[x, (y + 1) % height] >= 0
    )


def _place_thomas_species(
    rng: np.random.Generator,
    occupied: np.ndarray,
    species_id: int,
    x_bounds: tuple[int, int],
    n_parents: int,
    mean_offspring: float,
    sigma_r: float,
    width: int,
    height: int,
) -> list[tuple[int, int]]:
    placed: list[tuple[int, int]] = []
    px = rng.integers(x_bounds[0], x_bounds[1] + 1, size=n_parents)
    py = rng.integers(0, height, size=n_parents)
    for cx, cy in zip(px, py, strict=True):
        k = int(rng.poisson(mean_offspring))
        dx = rng.normal(0.0, sigma_r, size=k)
        dy = rng.normal(0.0, sigma_r, size=k)
        for ox, oy in zip(dx, dy, strict=True):
            tx = int(np.round(cx + ox)) % width
            ty = int(np.round(cy + oy)) % height
            if occupied[tx, ty] < 0:
                occupied[tx, ty] = species_id
                placed.append((tx, ty))
    return placed


def _place_p4_strip(
    rng: np.random.Generator,
    occupied: np.ndarray,
    width: int,
    height: int,
    scale_x: float,
) -> list[tuple[int, int]]:
    """Place herbaceous stripe p4 along dual Gaussian longitudinal bands."""
    p4_cells: list[tuple[int, int]] = []
    xs = np.arange(width, dtype=np.float64)
    c1 = max(0, min(width - 1, round(112 * scale_x)))
    c2 = max(0, min(width - 1, round(16 * scale_x)))
    d1 = np.minimum(np.abs(xs - c1), width - np.abs(xs - c1))
    d2 = np.minimum(np.abs(xs - c2), width - np.abs(xs - c2))
    prob_x = np.clip(
        0.24 * np.exp(-(d1**2) / (2.0 * (9.0 * scale_x) ** 2)) + 0.14 * np.exp(-(d2**2) / (2.0 * (7.0 * scale_x) ** 2)),
        0.0,
        0.35,
    )
    rolls = rng.random((width, height))
    for x in range(width):
        px_val = float(prob_x[x])
        if px_val <= 1e-4:
            continue
        for y in range(height):
            if occupied[x, y] < 0 and rolls[x, y] < px_val:
                occupied[x, y] = 4
                p4_cells.append((x, y))
    return p4_cells


def _scatter_patch_checkerboard(
    rng: np.random.Generator,
    occupied: np.ndarray,
    cx: int,
    cy: int,
    width: int,
    height: int,
    out: list[tuple[int, int]],
) -> None:
    """Populate diagonal non-CMN checkerboard points for species 5 within radius 4."""
    radius = 4
    for dx in range(-radius, radius + 1):
        for dy in range(-radius, radius + 1):
            if (dx + dy) % 2 != 0 or dx * dx + dy * dy > radius * radius or rng.random() > 0.72:
                continue
            tx = (cx + dx) % width
            ty = (cy + dy) % height
            if occupied[tx, ty] < 0 and not _has_cardinal_neighbor(occupied, tx, ty, width, height):
                occupied[tx, ty] = 5
                out.append((tx, ty))


def _place_p5_patches(
    rng: np.random.Generator,
    occupied: np.ndarray,
    width: int,
    height: int,
    scale_x: float,
    scale_area: float,
) -> list[tuple[int, int]]:
    """Place isolated Brassica p5 disturbance patches without cardinal neighbours."""
    p5_cells: list[tuple[int, int]] = []
    gap_e1 = max(0, min(width - 1, round(95 * scale_x)))
    gap_e2 = max(0, min(width - 1, round(25 * scale_x)))
    n_gap_patches = max(8, round(48 * scale_area))
    n_core_patches = max(3, round(12 * scale_area))
    gap_xs = np.concatenate([np.arange(0, gap_e2 + 1), np.arange(gap_e1, width)])
    core_xs = np.arange(gap_e2 + 1, gap_e1)
    patch_centers: list[tuple[int, int]] = []
    if len(gap_xs) > 0:
        patch_centers.extend(
            (int(cx), int(rng.integers(0, height))) for cx in rng.choice(gap_xs, size=n_gap_patches, replace=True)
        )
    if len(core_xs) > 0:
        patch_centers.extend(
            (int(cx), int(rng.integers(0, height))) for cx in rng.choice(core_xs, size=n_core_patches, replace=True)
        )
    for cx, cy in patch_centers:
        _scatter_patch_checkerboard(rng, occupied, cx, cy, width, height, p5_cells)
    return p5_cells


def _cardinal_cmn_degree(occupied: np.ndarray, x: int, y: int, width: int, height: int) -> int:
    """Count cardinal neighbours belonging to CMN-compatible guild IDs ``0..4``."""
    return sum(
        1 for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)) if 0 <= occupied[(x + dx) % width, (y + dy) % height] <= 4
    )


def _compute_cmn_stats(
    cells_by_sp: dict[int, list[tuple[int, int]]],
    occupied: np.ndarray,
    width: int,
    height: int,
) -> dict[int, dict[str, float]]:
    """Compute per-species mean CMN degree and connected percentage."""
    cmn_stats: dict[int, dict[str, float]] = {}
    for sp_id, coords in cells_by_sp.items():
        if sp_id == 5:
            cmn_stats[sp_id] = {"count": len(coords), "mean_deg": 0.0, "connected_pct": 0.0}
            continue
        degs = [_cardinal_cmn_degree(occupied, x, y, width, height) for x, y in coords]
        cmn_stats[sp_id] = {
            "count": len(coords),
            "mean_deg": float(np.mean(degs)) if degs else 0.0,
            "connected_pct": float(100.0 * np.mean([d > 0 for d in degs])) if degs else 0.0,
        }
    return cmn_stats


def _build_swarm_placements(
    rng: np.random.Generator,
    cells_by_sp: dict[int, list[tuple[int, int]]],
    occupied: np.ndarray,
    herbivores: list[HerbivoreSpeciesParams],
    width: int,
    height: int,
) -> list[InitialSwarmPlacement]:
    """Generate stratified initial herbivore swarms matched to ecotone host guilds."""

    def _pick_cells(pool: list[tuple[int, int]], count: int) -> list[tuple[int, int]]:
        chosen = rng.choice(len(pool), size=min(count, len(pool)), replace=False)
        return [pool[int(idx)] for idx in chosen]

    is_flagship = width == 256 and height == 256
    h0_n, h1_n, h2_n, h4_n = (14, 12, 18, 12) if is_flagship else (4, 4, 4, 4)
    p0_cells, p1_cells, p2_cells = cells_by_sp[0], cells_by_sp[1], cells_by_sp[2]
    p3_cells, p4_cells, p5_cells = cells_by_sp[3], cells_by_sp[4], cells_by_sp[5]
    connected_p2 = [(x, y) for x, y in p2_cells if _cardinal_cmn_degree(occupied, x, y, width, height) >= 2]
    if is_flagship:
        h3_coords = (
            _pick_cells(p2_cells, 4) + _pick_cells(p3_cells, 5) + _pick_cells(p4_cells, 3) + _pick_cells(p5_cells, 4)
        )
    else:
        h3_coords = _pick_cells(p3_cells, 2) + _pick_cells(p5_cells, 2)

    pop_scale = 1.0 if is_flagship else 0.5
    guild_coords: list[tuple[int, int, list[tuple[int, int]]]] = [
        (0, round(18 * pop_scale), _pick_cells(p0_cells + p1_cells, h0_n)),
        (1, round(16 * pop_scale), _pick_cells(p0_cells + p1_cells, h1_n)),
        (2, round(35 * pop_scale), _pick_cells(connected_p2 if len(connected_p2) >= h2_n else p2_cells, h2_n)),
        (3, round(18 * pop_scale), h3_coords),
        (4, round(16 * pop_scale), _pick_cells(p5_cells, h4_n)),
    ]
    swarm_placements: list[InitialSwarmPlacement] = []
    for h_id, pop, coords in guild_coords:
        e_init = round(pop * herbivores[h_id].energy_min * 1.4, 4)
        for sx_pos, sy_pos in coords:
            swarm_placements.append(
                InitialSwarmPlacement(species_id=h_id, x=sx_pos, y=sy_pos, population=pop, energy=e_init)
            )
    return swarm_placements


def _scale_coord(val: int, scale_x: float, width: int) -> int:
    """Scale an x-coordinate from the 256-cell canonical layout onto ``width``."""
    return max(0, min(width - 1, round(val * scale_x)))


def generate_spatial_layout(
    width: int, height: int, flora: list[FloraSpeciesParams], herbivores: list[HerbivoreSpeciesParams], seed: int = 42
) -> tuple[list[InitialPlantPlacement], list[InitialSwarmPlacement], dict[str, Any]]:
    """Generate stratified spatial plant and herbivore placements matching the ecotone report."""
    rng = np.random.default_rng(seed)
    occupied = np.full((width, height), -1, dtype=np.int32)
    scale_x = width / 256.0
    scale_area = (width * height) / (256.0 * 256.0)

    p0_cells = _place_thomas_species(
        rng,
        occupied,
        0,
        (_scale_coord(22, scale_x, width), _scale_coord(88, scale_x, width)),
        max(4, round(55 * scale_area)),
        65.0,
        4.2,
        width,
        height,
    )
    p1_cells = _place_thomas_species(
        rng,
        occupied,
        1,
        (_scale_coord(66, scale_x, width), _scale_coord(110, scale_x, width)),
        max(3, round(42 * scale_area)),
        55.0,
        3.8,
        width,
        height,
    )
    p4_cells = _place_p4_strip(rng, occupied, width, height, scale_x)
    p2_cells = _place_thomas_species(
        rng,
        occupied,
        2,
        (_scale_coord(114, scale_x, width), _scale_coord(244, scale_x, width)),
        max(5, round(65 * scale_area)),
        75.0,
        3.6,
        width,
        height,
    )
    p3_cells = _place_thomas_species(
        rng,
        occupied,
        3,
        (_scale_coord(106, scale_x, width), _scale_coord(248, scale_x, width)),
        max(6, round(85 * scale_area)),
        70.0,
        4.5,
        width,
        height,
    )
    p5_cells = _place_p5_patches(rng, occupied, width, height, scale_x, scale_area)

    cells_by_sp = {0: p0_cells, 1: p1_cells, 2: p2_cells, 3: p3_cells, 4: p4_cells, 5: p5_cells}
    plant_placements: list[InitialPlantPlacement] = [
        InitialPlantPlacement(species_id=sp_id, x=x, y=y, energy=flora[sp_id].base_energy)
        for sp_id, coords in cells_by_sp.items()
        for x, y in coords
    ]
    cmn_stats = _compute_cmn_stats(cells_by_sp, occupied, width, height)
    swarm_placements = _build_swarm_placements(rng, cells_by_sp, occupied, herbivores, width, height)

    summary = {
        "grid_width": width,
        "grid_height": height,
        "total_plants": len(plant_placements),
        "occupancy_pct": round(100.0 * len(plant_placements) / float(width * height), 2),
        "total_swarms": len(swarm_placements),
        "total_herbivore_individuals": sum(s.population for s in swarm_placements),
        "species_cmn_stats": cmn_stats,
    }
    return plant_placements, swarm_placements, summary


def build_config(width: int, height: int, seed: int = 42) -> tuple[SimulationConfig, dict[str, Any]]:
    """Build and Pydantic-validate a complete ecotone SimulationConfig."""
    flora = build_flora_species()
    herbivores = build_herbivore_species()
    diet = DietCompatibilityMatrix(
        rows=[
            [True, True, False, False, False, False],
            [True, True, False, False, False, False],
            [False, False, True, False, False, False],
            [False, False, True, True, True, True],
            [False, False, False, False, False, True],
        ]
    )
    plants, swarms, layout_stats = generate_spatial_layout(width, height, flora, herbivores, seed=seed)
    config = SimulationConfig(
        grid_width=width,
        grid_height=height,
        tile_carrying_capacity=60,
        max_ticks=4000,
        tick_rate_hz=10.0,
        num_signals=3,
        num_toxins=9,
        wind_x=0.878,
        wind_y=0.364,
        flora_species=flora,
        herbivore_species=herbivores,
        diet_matrix=diet,
        placement_mode="manual",
        initial_plants=plants,
        initial_swarms=swarms,
        mycorrhizal_inter_species=True,
        mycorrhizal_connection_cost=0.5,
        mycorrhizal_growth_interval_ticks=8,
        mycorrhizal_signal_velocity=2,
        chemotaxis_alpha=1.0,
        chemotaxis_beta=1.8,
        chemotaxis_decay=0.65,
        chemotaxis_truncate_threshold=1e-4,
        signal_decay_factor=0.82,
        substance_emit_rate=0.55,
        replay_backend="zarr",
    )
    validated = SimulationConfig.model_validate(config.model_dump())
    return validated, layout_stats


def main() -> None:
    """Generate and save validated 256x256 and 128x64 ecotone scenarios."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for w, h, fname in (
        (256, 256, "riparian_meadow_ecotone_256x256.json"),
        (128, 64, "riparian_meadow_ecotone_128x64_twin.json"),
    ):
        cfg, stats = build_config(w, h, seed=42)
        out_path = OUTPUT_DIR / fname
        out_path.write_text(json.dumps(cfg.model_dump(), indent=2), encoding="utf-8")
        print(f"Wrote {out_path} -> {json.dumps(stats)}")


if __name__ == "__main__":
    main()
