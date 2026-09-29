"""Unit tests for the data_pipeline transform logic."""

import polars as pl

from data_pipeline.transform import normalise_flora_dataframe, normalise_herbivore_dataframe


def test_normalise_flora_dataframe_error_handling() -> None:
    """Verify that _safe_get handles invalid input types cleanly for flora traits."""
    df = pl.DataFrame(
        [
            {
                "species_name": "Test Plant",
                "sla_cm2_per_g": "invalid_string",
                "seed_dry_mass_g": 1.0,
                "height_cm": 10.0,
                "leaf_tensile_n_mm2": None,
                "lignin_pct": "not_a_number",
                "ld50_mg_kg": "another_invalid",
            }
        ]
    )

    result = normalise_flora_dataframe(df)

    assert len(result) == 1

    result_dict = result.to_dicts()[0]

    # Check that fallback values were assigned properly
    assert "growth_rate" in result_dict
    assert isinstance(result_dict["growth_rate"], float)
    assert "max_energy" in result_dict
    assert isinstance(result_dict["max_energy"], float)
    assert "survival_threshold" in result_dict
    assert isinstance(result_dict["survival_threshold"], float)
    assert "seed_cost" in result_dict
    assert isinstance(result_dict["seed_cost"], float)
    assert "seed_dispersion_radius" in result_dict
    assert isinstance(result_dict["seed_dispersion_radius"], float)
    assert "mechanical_damage_per_bite" in result_dict
    assert isinstance(result_dict["mechanical_damage_per_bite"], float)


def test_normalise_herbivore_dataframe_error_handling() -> None:
    """Verify that _safe_get handles invalid input types cleanly for herbivore traits."""
    df = pl.DataFrame(
        [
            {
                "species_name": "Test Herbivore",
                "5-1_AdultBodyMass_g": "invalid_mass",
                "18-1_BasalMetRate_mLO2hr": None,
                "25-1_WeaningAge_d": "not_a_number",
                "10-1_PopulationGrpSize": "another_invalid",
            }
        ]
    )

    result = normalise_herbivore_dataframe(df)

    assert len(result) == 1

    result_dict = result.to_dicts()[0]

    # Check that fallback values were assigned properly
    assert "metabolism_upkeep" in result_dict
    assert isinstance(result_dict["metabolism_upkeep"], float)
    assert "consumption_rate" in result_dict
    assert isinstance(result_dict["consumption_rate"], float)
    assert "reproduction_energy_divisor" in result_dict
    assert isinstance(result_dict["reproduction_energy_divisor"], float)
    assert "split_population_threshold" in result_dict
    assert isinstance(result_dict["split_population_threshold"], float)
    assert "mitosis_threshold" in result_dict
    assert isinstance(result_dict["mitosis_threshold"], float)
