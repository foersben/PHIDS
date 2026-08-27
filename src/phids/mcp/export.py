# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Helper module for MCP server telemetry exports."""

from __future__ import annotations

import base64
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from phids.engine.batch.types import JSONValue, TelemetryRow
    from phids.engine.loop import SimulationLoop


def _export_csv(
    filtered_rows: list[TelemetryRow],
    normalized_data_type: str,
    tick_interval: int,
    columns: str | None,
) -> dict[str, JSONValue]:
    """Helper to handle CSV export generation."""
    from phids.telemetry.export.core import (
        aggregate_to_dataframe,
        decimate_dataframe,
        filter_dataframe_columns,
        telemetry_to_dataframe,
    )

    if normalized_data_type in ("timeseries", "defense_economy", "biomass_stack"):
        df = aggregate_to_dataframe(filtered_rows)  # type: ignore
    else:
        df = telemetry_to_dataframe(filtered_rows)

    if tick_interval > 1:
        df = decimate_dataframe(df, tick_interval)

    if columns:
        df = filter_dataframe_columns(df, columns)

    bytes_data = df.to_csv(index=False).encode("utf-8")
    return {"status": "success", "format": "csv", "data": bytes_data.decode("utf-8")}


def _export_tex_table(
    rows: list[TelemetryRow],
    tick_interval: int,
    columns: str | None,
    flora_ids: str | None,
    herbivore_ids: str | None,
) -> dict[str, JSONValue]:
    """Helper to handle TeX table export generation."""
    from phids.telemetry.export.latex import export_bytes_tex_table

    bytes_data = export_bytes_tex_table(
        rows,
        columns=columns,
        include_flora_ids=flora_ids,
        include_herbivore_ids=herbivore_ids,
        tick_interval=tick_interval,
    )
    return {"status": "success", "format": "tex_table", "data": bytes_data.decode("utf-8")}


def _export_tex_tikz(
    filtered_rows: list[TelemetryRow],
    normalized_data_type: str,
    flora_names: dict[int, str],
    herbivore_names: dict[int, str],
    plant_species_id: int,
    herbivore_species_id: int,
    flora_ids: str | None,
    herbivore_ids: str | None,
    title: str | None,
    x_label: str | None,
    y_label: str | None,
    x_max: float | None,
    y_max: float | None,
) -> dict[str, JSONValue]:
    """Helper to handle TeX TikZ export generation."""
    from phids.telemetry.export.tikz import generate_tikz_str

    tikz_str = generate_tikz_str(
        filtered_rows,
        normalized_data_type,
        flora_names=flora_names,
        herbivore_names=herbivore_names,
        plant_species_id=plant_species_id,
        herbivore_species_id=herbivore_species_id,
        include_flora_ids=flora_ids,
        include_herbivore_ids=herbivore_ids,
        title=title,
        x_label=x_label,
        y_label=y_label,
        x_max=x_max,
        y_max=y_max,
    )
    return {"status": "success", "format": "tex_tikz", "data": tikz_str}


def _export_png(
    filtered_rows: list[TelemetryRow],
    normalized_data_type: str,
    flora_names: dict[int, str],
    herbivore_names: dict[int, str],
    plant_species_id: int,
    herbivore_species_id: int,
    flora_ids: str | None,
    herbivore_ids: str | None,
    title: str | None,
    x_label: str | None,
    y_label: str | None,
    x_max: float | None,
    y_max: float | None,
) -> dict[str, JSONValue]:
    """Helper to handle PNG export generation."""
    from phids.telemetry.export.png import generate_png_bytes

    bytes_data = generate_png_bytes(
        filtered_rows,
        normalized_data_type,
        flora_names=flora_names,
        herbivore_names=herbivore_names,
        plant_species_id=plant_species_id,
        herbivore_species_id=herbivore_species_id,
        include_flora_ids=flora_ids,
        include_herbivore_ids=herbivore_ids,
        title=title,
        x_label=x_label,
        y_label=y_label,
        x_max=x_max,
        y_max=y_max,
    )
    return {"status": "success", "format": "png", "data": base64.b64encode(bytes_data).decode("utf-8")}


def execute_export_telemetry_data(
    loop: SimulationLoop,
    format_type: str,
    data_type: str = "timeseries",
    tick_interval: int = 1,
    plant_species_id: int = 0,
    herbivore_species_id: int = 0,
    columns: str | None = None,
    flora_ids: str | None = None,
    herbivore_ids: str | None = None,
    title: str | None = None,
    x_label: str | None = None,
    y_label: str | None = None,
    x_max: float | None = None,
    y_max: float | None = None,
) -> dict[str, JSONValue]:
    """Execute the core logic of telemetry export for the MCP server.

    Args:
        loop: The active simulation loop.
        format_type: 'csv', 'tex_table', 'tex_tikz', or 'png'.
        data_type: 'timeseries', 'phasespace', 'defense_economy', 'biomass_stack', 'metabolic'.
        tick_interval: Decimation factor for large datasets (e.g. 10 = every 10th tick).
        plant_species_id: Flora species ID for phase-space axes.
        herbivore_species_id: Herbivore species ID for phase-space axes.
        columns: Comma-separated list of columns to include.
        flora_ids: Comma-separated list of flora species to include.
        herbivore_ids: Comma-separated list of herbivore species to include.
        title: Chart title override.
        x_label: X-axis label override.
        y_label: Y-axis label override.
        x_max: X-axis scale maximum.
        y_max: Y-axis scale maximum.

    Returns:
        dict[str, JSONValue]: A dictionary containing ``status``, ``format``, and ``data``.
    """
    normalized_data_type = "defense_economy" if data_type == "metabolic" else data_type
    valid_data_types = {"timeseries", "phasespace", "defense_economy", "biomass_stack"}

    if normalized_data_type not in valid_data_types:
        return {"status": "error", "message": f"Invalid data_type. Must be one of {valid_data_types}"}

    if format_type not in {"csv", "tex_table", "tex_tikz", "png"}:
        return {"status": "error", "message": "Invalid format. Must be csv, tex_table, tex_tikz, or png."}

    try:
        from phids.telemetry.export.core import filter_telemetry_rows

        rows = loop.telemetry._rows
        flora_names = {sp.species_id: sp.name for sp in loop.config.flora_species}
        herbivore_names = {sp.species_id: sp.name for sp in loop.config.herbivore_species}

        filtered_rows = filter_telemetry_rows(rows, flora_ids=flora_ids, herbivore_ids=herbivore_ids)

        if format_type == "csv":
            return _export_csv(
                filtered_rows=filtered_rows,
                normalized_data_type=normalized_data_type,
                tick_interval=tick_interval,
                columns=columns,
            )

        elif format_type == "tex_table":
            return _export_tex_table(
                rows=rows,
                tick_interval=tick_interval,
                columns=columns,
                flora_ids=flora_ids,
                herbivore_ids=herbivore_ids,
            )

        elif format_type == "tex_tikz":
            return _export_tex_tikz(
                filtered_rows=filtered_rows,
                normalized_data_type=normalized_data_type,
                flora_names=flora_names,
                herbivore_names=herbivore_names,
                plant_species_id=plant_species_id,
                herbivore_species_id=herbivore_species_id,
                flora_ids=flora_ids,
                herbivore_ids=herbivore_ids,
                title=title,
                x_label=x_label,
                y_label=y_label,
                x_max=x_max,
                y_max=y_max,
            )

        elif format_type == "png":
            return _export_png(
                filtered_rows=filtered_rows,
                normalized_data_type=normalized_data_type,
                flora_names=flora_names,
                herbivore_names=herbivore_names,
                plant_species_id=plant_species_id,
                herbivore_species_id=herbivore_species_id,
                flora_ids=flora_ids,
                herbivore_ids=herbivore_ids,
                title=title,
                x_label=x_label,
                y_label=y_label,
                x_max=x_max,
                y_max=y_max,
            )

    except Exception as e:
        return {"status": "error", "message": f"Export generation failed: {e}"}
    return {"status": "error", "message": "Unknown format"}
