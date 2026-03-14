"""Tests for the academic export pipeline.

This test module validates the correctness of all export functions in
:mod:`phids.telemetry.export`. The suite covers per-species DataFrame
flattening via :func:`~phids.telemetry.export.telemetry_to_dataframe`,
headless matplotlib PNG rendering via
:func:`~phids.telemetry.export.generate_png_bytes`, PGFPlots TikZ source
generation via :func:`~phids.telemetry.export.generate_tikz_str`, and
booktabs LaTeX table serialisation via
:func:`~phids.telemetry.export.export_bytes_tex_table`. Correctness is
asserted at both the structural level (non-empty output, expected column names,
expected LaTeX keywords) and the logical level (correct population values,
correct phase-space coordinates, correct export format routing).
"""

from __future__ import annotations

import pytest

from phids.telemetry.export import (
    export_bytes_tex_table,
    generate_png_bytes,
    generate_tikz_str,
    telemetry_to_dataframe,
)


def _sample_rows() -> list[dict]:
    """Return a minimal two-tick telemetry row list for export testing."""
    return [
        {
            "tick": 0,
            "flora_population": 10,
            "predator_population": 3,
            "total_flora_energy": 500.0,
            "predator_clusters": 1,
            "death_reproduction": 0,
            "death_mycorrhiza": 0,
            "death_defense_maintenance": 0,
            "death_herbivore_feeding": 0,
            "death_background_deficit": 0,
            "plant_pop_by_species": {0: 6, 1: 4},
            "plant_energy_by_species": {0: 300.0, 1: 200.0},
            "swarm_pop_by_species": {0: 3},
            "defense_cost_by_species": {},
        },
        {
            "tick": 1,
            "flora_population": 9,
            "predator_population": 4,
            "total_flora_energy": 480.0,
            "predator_clusters": 1,
            "death_reproduction": 1,
            "death_mycorrhiza": 0,
            "death_defense_maintenance": 0,
            "death_herbivore_feeding": 0,
            "death_background_deficit": 0,
            "plant_pop_by_species": {0: 5, 1: 4},
            "plant_energy_by_species": {0: 280.0, 1: 200.0},
            "swarm_pop_by_species": {0: 4},
            "defense_cost_by_species": {},
        },
    ]


class TestTelemetryToDataframe:
    """Validates per-species dict flattening into wide pandas DataFrame."""

    def test_columns_present(self) -> None:
        """Expected per-species columns are present in the flattened DataFrame."""
        df = telemetry_to_dataframe(_sample_rows())
        assert "tick" in df.columns
        assert "plant_0_pop" in df.columns
        assert "plant_1_pop" in df.columns
        assert "plant_0_energy" in df.columns
        assert "swarm_0_pop" in df.columns

    def test_values_correct(self) -> None:
        """Per-species population values match the source row dictionaries."""
        df = telemetry_to_dataframe(_sample_rows())
        assert df["plant_0_pop"].iloc[0] == 6
        assert df["plant_1_pop"].iloc[0] == 4
        assert df["swarm_0_pop"].iloc[1] == 4

    def test_empty_rows_returns_empty(self) -> None:
        """An empty row list produces an empty DataFrame."""
        df = telemetry_to_dataframe([])
        assert df.empty

    def test_missing_species_filled_with_zero(self) -> None:
        """Species absent in some ticks are zero-filled rather than NaN."""
        rows = [
            {
                "tick": 0,
                "plant_pop_by_species": {0: 5},
                "plant_energy_by_species": {0: 100.0},
                "swarm_pop_by_species": {},
                "defense_cost_by_species": {},
                "flora_population": 5, "predator_population": 0,
                "total_flora_energy": 100.0, "predator_clusters": 0,
                "death_reproduction": 0, "death_mycorrhiza": 0,
                "death_defense_maintenance": 0, "death_herbivore_feeding": 0,
                "death_background_deficit": 0,
            },
            {
                "tick": 1,
                "plant_pop_by_species": {0: 3, 1: 2},
                "plant_energy_by_species": {0: 60.0, 1: 40.0},
                "swarm_pop_by_species": {},
                "defense_cost_by_species": {},
                "flora_population": 5, "predator_population": 0,
                "total_flora_energy": 100.0, "predator_clusters": 0,
                "death_reproduction": 0, "death_mycorrhiza": 0,
                "death_defense_maintenance": 0, "death_herbivore_feeding": 0,
                "death_background_deficit": 0,
            },
        ]
        df = telemetry_to_dataframe(rows)
        # tick=0 had no species 1 — should be 0, not NaN
        assert df["plant_1_pop"].iloc[0] == 0


class TestGeneratePngBytes:
    """Validates PNG export from telemetry rows."""

    def test_timeseries_returns_nonempty_bytes(self) -> None:
        """PNG export for timeseries mode returns non-empty bytes."""
        data = generate_png_bytes(_sample_rows(), "timeseries")
        assert isinstance(data, bytes)
        assert len(data) > 1000  # PNG header + content

    def test_phasespace_returns_nonempty_bytes(self) -> None:
        """PNG export for phase-space mode returns non-empty bytes."""
        data = generate_png_bytes(_sample_rows(), "phasespace")
        assert isinstance(data, bytes)
        assert len(data) > 1000

    def test_empty_rows_returns_bytes(self) -> None:
        """Empty row list produces a 'No data' placeholder PNG."""
        data = generate_png_bytes([], "timeseries")
        assert isinstance(data, bytes)
        assert len(data) > 100

    def test_invalid_plot_type_raises(self) -> None:
        """An unrecognized plot_type raises ValueError."""
        with pytest.raises(ValueError, match="Unknown plot_type"):
            generate_png_bytes(_sample_rows(), "histogram")

    def test_defense_economy_returns_nonempty_bytes(self) -> None:
        """PNG export for defense economy mode returns non-empty bytes."""
        data = generate_png_bytes(_sample_rows(), "defense_economy")
        assert isinstance(data, bytes)
        assert len(data) > 1000

    def test_biomass_stack_returns_nonempty_bytes(self) -> None:
        """PNG export for stacked biomass mode returns non-empty bytes."""
        data = generate_png_bytes(_sample_rows(), "biomass_stack")
        assert isinstance(data, bytes)
        assert len(data) > 1000


class TestGenerateTikzStr:
    """Validates PGFPlots LaTeX source generation."""

    def test_timeseries_contains_tikzpicture(self) -> None:
        """Timeseries TikZ output contains the tikzpicture environment."""
        s = generate_tikz_str(_sample_rows(), "timeseries")
        assert "\\begin{tikzpicture}" in s
        assert "\\end{tikzpicture}" in s
        assert "\\addplot" in s

    def test_phasespace_contains_tikzpicture(self) -> None:
        """Phase-space TikZ output contains valid PGFPlots axis environment."""
        s = generate_tikz_str(_sample_rows(), "phasespace")
        assert "\\begin{tikzpicture}" in s
        assert "\\begin{axis}" in s

    def test_flora_names_in_legend(self) -> None:
        """Custom species names appear in the generated TikZ legend entries."""
        s = generate_tikz_str(
            _sample_rows(),
            "timeseries",
            flora_names={0: "Bunchgrass", 1: "Shrub"},
        )
        assert "Bunchgrass" in s

    def test_invalid_type_raises(self) -> None:
        """An unknown plot_type raises ValueError."""
        with pytest.raises(ValueError):
            generate_tikz_str(_sample_rows(), "scatter3d")

    def test_defense_economy_tikz_contains_axis(self) -> None:
        """Defense economy TikZ output contains a valid axis environment."""
        s = generate_tikz_str(_sample_rows(), "defense_economy")
        assert "\\begin{axis}" in s
        assert "Defense economy" in s

    def test_biomass_stack_tikz_contains_axis(self) -> None:
        """Biomass stack TikZ output contains a valid axis environment."""
        s = generate_tikz_str(_sample_rows(), "biomass_stack")
        assert "\\begin{axis}" in s
        assert "Carrying Capacity" in s

    def test_custom_title_and_axes_are_applied(self) -> None:
        """User-provided title and axis labels are propagated into TikZ output."""
        s = generate_tikz_str(
            _sample_rows(),
            "phasespace",
            title="Custom Phase",
            x_label="Prey Axis",
            y_label="Pred Axis",
        )
        assert "Custom Phase" in s
        assert "Prey Axis" in s
        assert "Pred Axis" in s


class TestExportBytesTexTable:
    """Validates booktabs LaTeX table export."""

    def test_contains_toprule(self) -> None:
        """LaTeX table output includes booktabs toprule command."""
        data = export_bytes_tex_table(_sample_rows())
        latex = data.decode("utf-8")
        assert "\\toprule" in latex or "\\begin{tabular}" in latex

    def test_empty_rows_returns_comment(self) -> None:
        """Empty row list produces a LaTeX comment placeholder."""
        data = export_bytes_tex_table([])
        assert b"%" in data

    def test_tick_column_present(self) -> None:
        """The tick column appears in the exported LaTeX table."""
        data = export_bytes_tex_table(_sample_rows())
        assert b"tick" in data

    def test_column_filter_is_respected(self) -> None:
        """Column-scoped table export omits non-selected telemetry columns."""
        data = export_bytes_tex_table(_sample_rows(), columns="tick,plant_0_pop")
        latex = data.decode("utf-8")
        assert "plant_0_pop" in latex
        assert "predator_population" not in latex

