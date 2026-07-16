# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Mathematical normalisation and parameter mapping for the PHIDS ETL pipeline.

Transforms raw empirical trait values from physical units into unitless
engine-compatible float bounds.  Every output value is guaranteed to lie
within the interval [1e-4, 1.0] (flora/herbivore scalar params) or within
extended engine bounds (energy, population) as documented per parameter.

Design rationale
----------------
All scaling uses **Min-Max normalisation** anchored to empirically-informed
global extrema rather than dataset-local min/max.  This prevents single-dataset
outliers from collapsing the parameter range and ensures consistent semantics
across pipeline runs with different species selections.

The global extrema are derived from:
- TRY trait distributions (Kattge et al. 2020, GCB)
- PanTHERIA species range (Jones et al. 2009, Ecology)
- EFSA/Merck Index toxicology data

Subnormal protection
--------------------
Any value computed below 1e-4 is clamped to 1e-4.
Any value computed above the documented upper bound is clamped to that bound.
This is mandatory: the Numba-compiled PDE and flow-field kernels will suffer
catastrophic hardware stalls on subnormal IEEE 754 floats.

Parameter mapping table
-----------------------
| Raw trait (unit)                  | Target param             | Output range |
|-----------------------------------|--------------------------|--------------|
| SLA (cm²/g)                       | growth_rate              | [1e-4, 1.0]  |
| seed_dry_mass (g) + height (cm)   | max_energy               | [5.0, 100.0] |
| (derived from max_energy)         | survival_threshold       | 10% of max   |
| (derived from height)             | seed_dispersion_radius   | [1.0, 5.0]   |
| leaf_tensile_strength (N/mm²)     | mechanical_damage_per_bite| [0.0, 0.30]  |
| lignin_pct_dryweight (%)          | digestibility_modifier   | [0.5, 1.0]   |
| LD50 (mg/kg, oral rat)            | lethality_rate           | [0.1, 10.0]  |
| molecular_weight (g/mol)          | diffusion_coefficient    | [0.01, 0.90] |
| BMR (mLO2/hr) + body_mass (g)     | metabolism_upkeep        | [0.05, 0.50] |
| adult_body_mass (g)               | consumption_rate         | [0.5, 5.0]   |
| weaning_age (days)                | reproduction_energy_divisor| [2.0, 20.0] |
| social_group_size (individuals)   | split_population_threshold| [10.0, 200.0]|
"""

from __future__ import annotations

import logging
import math

import polars as pl

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Global empirical extrema
# ---------------------------------------------------------------------------

# SLA: global range from TRY (Poorter et al. 2009, New Phytologist)
# Min: 0.5 cm²/g (highly sclerophyllous Nardus stricta)
# Max: 60 cm²/g (thin-leaved pioneer herbs like Arabidopsis)
_SLA_MIN: float = 0.5
_SLA_MAX: float = 60.0

# Seed dry mass: global range (Moles et al. 2005, Science)
# Min: 0.001 g (Orchidaceae dust seeds)
# Max: 500 g (large-seeded trees, e.g. Quercus)
_SEED_MASS_MIN: float = 0.001
_SEED_MASS_MAX: float = 500.0

# Plant height: global range (Kunstler et al. 2016, Nature)
# Min: 1 cm (moss/prostrate herbs)
# Max: 5000 cm (50 m, large canopy trees)
_HEIGHT_MIN: float = 1.0
_HEIGHT_MAX: float = 5000.0

# Leaf tensile strength: global range (Wright et al. 2004, Nature)
# Min: 0.01 N/mm² (non-sclerophyllous herbs)
# Max: 15 N/mm² (highly sclerophyllous leaves, silica-rich grasses)
_TENSILE_MIN: float = 0.01
_TENSILE_MAX: float = 15.0

# Lignin % dry weight: typical range (van Soest 1994)
# Min: 1% (young leaves of fast growers)
# Max: 45% (woody climax species, bark-heavy conifers)
_LIGNIN_MIN: float = 1.0
_LIGNIN_MAX: float = 45.0

# LD50 (mg/kg oral rat): range from Merck Index / EFSA
# Min: 0.3 mg/kg (aconitine - among most toxic plant compounds)
# Max: 5000 mg/kg (tannins - low acute toxicity)
_LD50_MIN: float = 0.3
_LD50_MAX: float = 5000.0

# Adult body mass (g): mammalian herbivore range from PanTHERIA
# Min: 10 g (small rodent Microtus)
# Max: 900000 g (900 kg, Bison bison)
_BODY_MASS_MIN: float = 10.0
_BODY_MASS_MAX: float = 900_000.0

# Basal metabolic rate (mLO2/hr): range from PanTHERIA
# Using Kleiber scaling: BMR ≈ 3.8 * M^0.75 (kcal/day)
# Min: ~0.05 (small insectivore, ~10g)
# Max: ~20000 (large bovid, ~500kg)
_BMR_MIN: float = 0.05
_BMR_MAX: float = 20_000.0

# Weaning age (days): range from PanTHERIA
# Min: 14 days (small rodents)
# Max: 730 days (large primates / elephants)
_WEAN_MIN: float = 14.0
_WEAN_MAX: float = 730.0

# Social group size (individuals): range from PanTHERIA
# Min: 1 (solitary species)
# Max: 1000+ (migratory ungulates, locust swarms)
_GROUP_MIN: float = 1.0
_GROUP_MAX: float = 1000.0

# Flush-to-zero floor: any computed value below this is clamped
_FTZ_FLOOR: float = 1e-4


# ---------------------------------------------------------------------------
# Flora normalisation
# ---------------------------------------------------------------------------


def normalise_growth_rate(sla_cm2_per_g: float | None) -> float:
    """Map Specific Leaf Area to photosynthetic growth_rate in [1e-4, 1.0].

    Args:
        sla_cm2_per_g: SLA measurement in cm²/g. None uses median fallback.

    Returns:
        Normalised growth_rate float.

    """
    if sla_cm2_per_g is None:
        return 0.10  # ecologically reasonable median
    return _minmax_clamp(sla_cm2_per_g, _SLA_MIN, _SLA_MAX, out_min=_FTZ_FLOOR, out_max=1.0)


def normalise_max_energy(seed_mass_g: float | None, height_cm: float | None) -> float:
    """Map seed dry mass and canopy height to max_energy in [5.0, 100.0].

    Uses a weighted geometric mean to combine the two size proxies.
    Seed mass contributes 60%, height 40% (seed mass is a stronger biomass proxy).

    Args:
        seed_mass_g: Seed dry mass in grams. None uses median.
        height_cm: Maximum vegetative height in cm. None uses median.

    Returns:
        Normalised max_energy float in [5.0, 100.0].

    """
    if seed_mass_g is None:
        seed_mass_g = 1.0  # median broadleaf tree seed mass
    if height_cm is None:
        height_cm = 150.0  # median shrub/tree height

    norm_seed = _log_minmax_clamp(seed_mass_g, _SEED_MASS_MIN, _SEED_MASS_MAX)
    norm_height = _log_minmax_clamp(height_cm, _HEIGHT_MIN, _HEIGHT_MAX)
    # Weighted blend
    combined = 0.6 * norm_seed + 0.4 * norm_height
    return round(max(5.0, min(100.0, combined * 95.0 + 5.0)), 4)


def normalise_mechanical_damage(tensile_strength_n_mm2: float | None) -> float:
    """Map leaf tensile strength to mechanical_damage_per_bite in [0.0, 0.30].

    Args:
        tensile_strength_n_mm2: Tensile strength in N/mm². None → 0.0 (no defense).

    Returns:
        mechanical_damage_per_bite float.

    """
    if tensile_strength_n_mm2 is None:
        return 0.0
    return round(_minmax_clamp(tensile_strength_n_mm2, _TENSILE_MIN, _TENSILE_MAX, out_min=0.0, out_max=0.30), 4)


def normalise_digestibility(lignin_pct: float | None) -> float:
    """Map lignin content to digestibility_modifier in [0.5, 1.0].

    Higher lignin → lower digestibility → modifier closer to 0.5.
    Modifier is *inverted* so that high lignin = penalty.

    Args:
        lignin_pct: Lignin as % dry weight. None → 1.0 (fully digestible).

    Returns:
        digestibility_modifier float in [0.5, 1.0].

    """
    if lignin_pct is None:
        return 1.0
    # Normalise lignin to [0, 1] then invert and scale to [0.5, 1.0]
    norm = _minmax_clamp(lignin_pct, _LIGNIN_MIN, _LIGNIN_MAX, out_min=0.0, out_max=1.0)
    return round(1.0 - norm * 0.5, 4)  # high lignin → 0.5; low lignin → 1.0


def normalise_lethality_rate(ld50_mg_kg: float | None) -> float:
    """Map LD50 (mg/kg oral rat) to lethality_rate in [0.1, 10.0].

    LD50 is *inverted*: lower LD50 = more toxic = higher lethality_rate.
    A log-scale inversion is used to handle the extreme range (0.3–5000).

    Args:
        ld50_mg_kg: Median lethal dose in mg/kg. None → 0.0 (non-toxic).

    Returns:
        lethality_rate float in [0.1, 10.0], or 0.0 if no toxin data.

    """
    if ld50_mg_kg is None:
        return 0.0
    # Log-scale: lower LD50 → higher toxicity score
    log_ld50 = math.log10(max(ld50_mg_kg, 0.01))
    log_min = math.log10(_LD50_MIN)
    log_max = math.log10(_LD50_MAX)
    # Invert: aconitine (LD50=0.36) → ~10.0; tannins (LD50=5000) → ~0.1
    norm = (log_ld50 - log_min) / (log_max - log_min)
    inverted = 1.0 - norm
    return round(max(0.1, min(10.0, inverted * 10.0)), 4)


def normalise_seed_dispersion_radius(height_cm: float | None) -> float:
    """Map plant height to seed_dispersion_radius in [1.0, 5.0].

    Taller plants tend to have wider seed dispersal (wind, ballistic).

    Args:
        height_cm: Maximum vegetative height in cm. None → 1.0.

    Returns:
        seed_dispersion_radius float in [1.0, 5.0].

    """
    if height_cm is None:
        return 1.0
    return round(_log_minmax_clamp(height_cm, _HEIGHT_MIN, _HEIGHT_MAX, out_min=1.0, out_max=5.0), 4)


# ---------------------------------------------------------------------------
# Herbivore normalisation
# ---------------------------------------------------------------------------


def normalise_metabolism_upkeep(bmr_mlo2_hr: float | None, body_mass_g: float | None) -> float:
    """Map basal metabolic rate to metabolism_upkeep in [0.05, 0.50].

    Uses Kleiber's Law to scale BMR relative to body mass:
        mass-specific BMR = BMR / (M^0.75)

    This captures the key biological invariant that large animals have
    lower mass-specific metabolic rates.

    Args:
        bmr_mlo2_hr: Basal metabolic rate in mLO2/hr.
        body_mass_g: Adult body mass in grams.

    Returns:
        metabolism_upkeep float in [0.05, 0.50].

    """
    if bmr_mlo2_hr is None or body_mass_g is None:
        return 0.10  # median fallback
    # Convert mLO2/hr to kcal/day: 1 mLO2 = ~0.0048 kcal; * 24
    kcal_per_day = bmr_mlo2_hr * 0.0048 * 24.0
    # Mass-specific BMR (kcal/day/g)
    mass_specific = kcal_per_day / max(body_mass_g**0.75, 1.0)
    # Normalise using log scale across mammalian range
    return round(_log_minmax_clamp(mass_specific, 1e-5, 1.0, out_min=0.05, out_max=0.50), 4)


def normalise_consumption_rate(body_mass_g: float | None) -> float:
    """Map adult body mass to consumption_rate in [0.5, 5.0].

    Larger herbivores can physically consume more biomass per interaction phase.
    Scaled log-linearly across the mammalian body mass range.

    Args:
        body_mass_g: Adult body mass in grams.

    Returns:
        consumption_rate float in [0.5, 5.0].

    """
    if body_mass_g is None:
        return 1.5  # median
    return round(_log_minmax_clamp(body_mass_g, _BODY_MASS_MIN, _BODY_MASS_MAX, out_min=0.5, out_max=5.0), 4)


def normalise_reproduction_energy_divisor(weaning_age_days: float | None) -> float:
    """Map weaning age to reproduction_energy_divisor in [2.0, 20.0].

    Longer weaning periods indicate higher parental investment, which translates
    to a larger caloric surplus required before a swarm can split.

    Args:
        weaning_age_days: Age of weaning in days.

    Returns:
        reproduction_energy_divisor float in [2.0, 20.0].

    """
    if weaning_age_days is None:
        return 5.0
    return round(_minmax_clamp(weaning_age_days, _WEAN_MIN, _WEAN_MAX, out_min=2.0, out_max=20.0), 4)


def normalise_split_population_threshold(group_size: float | None) -> float:
    """Map social group size to split_population_threshold in [10.0, 200.0].

    Args:
        group_size: Typical social group size in individuals.

    Returns:
        split_population_threshold float in [10.0, 200.0].

    """
    if group_size is None:
        return 50.0
    return round(_log_minmax_clamp(group_size, _GROUP_MIN, _GROUP_MAX, out_min=10.0, out_max=200.0), 4)


# ---------------------------------------------------------------------------
# DataFrame-level normalisation entrypoints
# ---------------------------------------------------------------------------


def normalise_flora_dataframe(df: pl.DataFrame) -> pl.DataFrame:
    """Apply all flora normalisation functions to a Polars DataFrame.

    Expected input columns (all optional, fallbacks apply for None):
        sla_cm2_per_g, seed_dry_mass_g, height_cm, leaf_tensile_n_mm2,
        lignin_pct

    Args:
        df: Input DataFrame with raw trait columns.

    Returns:
        DataFrame with additional engine-parameter columns.

    """
    logger.info("Normalising flora traits for %d species", len(df))

    def _safe_get(row: dict[str, object], key: str) -> float | None:
        val = row.get(key)
        if val is None:
            return None
        try:
            return float(val)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return None

    records = []
    for row in df.to_dicts():
        sla = _safe_get(row, "sla_cm2_per_g")
        seed = _safe_get(row, "seed_dry_mass_g")
        height = _safe_get(row, "height_cm")
        tensile = _safe_get(row, "leaf_tensile_n_mm2")
        lignin = _safe_get(row, "lignin_pct")
        ld50 = _safe_get(row, "ld50_mg_kg")

        max_e = normalise_max_energy(seed, height)
        records.append(
            {
                **row,
                "growth_rate": normalise_growth_rate(sla),
                "max_energy": max_e,
                "survival_threshold": round(max_e * 0.10, 4),
                "seed_cost": round(max_e * 0.25, 4),
                "seed_dispersion_radius": normalise_seed_dispersion_radius(height),
                "mechanical_damage_per_bite": normalise_mechanical_damage(tensile),
                "digestibility_modifier": normalise_digestibility(lignin),
                "lethality_rate": normalise_lethality_rate(ld50),
            }
        )

    return pl.DataFrame(records)


def normalise_herbivore_dataframe(df: pl.DataFrame) -> pl.DataFrame:
    """Apply all herbivore normalisation functions to a Polars DataFrame.

    Expected input columns (all optional):
        body_mass_g, bmr_mlo2_hr, weaning_age_d, group_size

    Args:
        df: Input DataFrame with raw PanTHERIA/ADW columns.

    Returns:
        DataFrame with engine-parameter columns appended.

    """
    logger.info("Normalising herbivore traits for %d species", len(df))

    def _safe_get(row: dict[str, object], key: str) -> float | None:
        val = row.get(key)
        if val is None:
            return None
        try:
            return float(val)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return None

    records = []
    for row in df.to_dicts():
        mass = _safe_get(row, "5-1_AdultBodyMass_g")
        bmr = _safe_get(row, "18-1_BasalMetRate_mLO2hr")
        wean = _safe_get(row, "25-1_WeaningAge_d")
        grp = _safe_get(row, "10-1_PopulationGrpSize")

        records.append(
            {
                **row,
                "metabolism_upkeep": normalise_metabolism_upkeep(bmr, mass),
                "consumption_rate": normalise_consumption_rate(mass),
                "reproduction_energy_divisor": normalise_reproduction_energy_divisor(wean),
                "split_population_threshold": normalise_split_population_threshold(grp),
                "mitosis_threshold": normalise_split_population_threshold(grp) * 2.0,
                "split_ratio": 0.5,  # symmetric split - engine default
            }
        )

    return pl.DataFrame(records)


# ---------------------------------------------------------------------------
# Utility: normalisation math
# ---------------------------------------------------------------------------


def _minmax_clamp(
    value: float,
    in_min: float,
    in_max: float,
    out_min: float = _FTZ_FLOOR,
    out_max: float = 1.0,
) -> float:
    """Linear Min-Max scale ``value`` from [in_min, in_max] to [out_min, out_max].

    Args:
        value: Raw input value.
        in_min: Lower bound of input range.
        in_max: Upper bound of input range.
        out_min: Lower bound of output range.
        out_max: Upper bound of output range.

    Returns:
        Scaled and clamped float value.

    """
    if in_max == in_min:
        return out_min
    norm = (value - in_min) / (in_max - in_min)
    scaled = norm * (out_max - out_min) + out_min
    return float(max(out_min, min(out_max, scaled)))


def _log_minmax_clamp(
    value: float,
    in_min: float,
    in_max: float,
    out_min: float = _FTZ_FLOOR,
    out_max: float = 1.0,
) -> float:
    """Log-scale Min-Max normalise for quantities spanning multiple orders of magnitude.

    Args:
        value: Raw input value (must be > 0).
        in_min: Lower bound of input range (must be > 0).
        in_max: Upper bound of input range.
        out_min: Lower bound of output range.
        out_max: Upper bound of output range.

    Returns:
        Scaled and clamped float value.

    """
    log_val = math.log10(max(value, 1e-10))
    log_min = math.log10(max(in_min, 1e-10))
    log_max = math.log10(max(in_max, 1e-10))
    return _minmax_clamp(log_val, log_min, log_max, out_min, out_max)
