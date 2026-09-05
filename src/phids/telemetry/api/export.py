# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Export helpers for telemetry data formatting.

This module provides internal helpers to generate structured strings (CSV,
LaTeX, TikZ) and binary images (PNG) representing telemetry records. These
functions are stateless and designed to reduce cognitive complexity in route
handlers or server wrappers by abstracting away data filtering, downsampling,
and specific exporter library calls.
"""

from __future__ import annotations

import base64
from typing import Any


def _generate_csv_export(
    filtered_rows: list[dict[str, Any]],
    normalized_data_type: str,
    tick_interval: int,
    columns: str | None,
) -> dict[str, Any]:
    """Generate CSV formatted telemetry.

    Args:
        filtered_rows: The raw rows to process.
        normalized_data_type: The dataset shape type.
        tick_interval: Sampling interval factor.
        columns: Optional comma separated column names to retain.

    Returns:
        The operation status and string-encoded CSV data.
    """
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


def _generate_tex_table_export(
    rows: list[dict[str, Any]],
    columns: str | None,
    flora_ids: str | None,
    herbivore_ids: str | None,
    tick_interval: int,
) -> dict[str, Any]:
    """Generate LaTeX tabular representation of telemetry.

    Args:
        rows: Unfiltered original rows.
        columns: Optional explicit columns.
        flora_ids: Flora species ID filter.
        herbivore_ids: Herbivore species ID filter.
        tick_interval: Resampling interval.

    Returns:
        The operation status and LaTeX formatted string data.
    """
    from phids.telemetry.export.latex import export_bytes_tex_table

    bytes_data = export_bytes_tex_table(
        rows,
        columns=columns,
        include_flora_ids=flora_ids,
        include_herbivore_ids=herbivore_ids,
        tick_interval=tick_interval,
    )
    return {"status": "success", "format": "tex_table", "data": bytes_data.decode("utf-8")}


def _generate_tex_tikz_export(
    filtered_rows: list[dict[str, Any]],
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
) -> dict[str, Any]:
    """Generate TikZ plot rendering representation of telemetry.

    Args:
        filtered_rows: Pruned telemetry lines.
        normalized_data_type: The dataset layout pattern.
        flora_names: Mappings from ID to display string.
        herbivore_names: Mappings from ID to display string.
        plant_species_id: Plant metric selector.
        herbivore_species_id: Herbivore metric selector.
        flora_ids: Included flora.
        herbivore_ids: Included herbivores.
        title: Plot title text.
        x_label: Horizontal axis text.
        y_label: Vertical axis text.
        x_max: Max X range.
        y_max: Max Y range.

    Returns:
        The operation status and TikZ macro payload.
    """
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


def _generate_png_export(
    filtered_rows: list[dict[str, Any]],
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
) -> dict[str, Any]:
    """Generate raster PNG plot representation of telemetry.

    Args:
        filtered_rows: Processed simulation data rows.
        normalized_data_type: Base graph configuration identifier.
        flora_names: Mappings from ID to display string.
        herbivore_names: Mappings from ID to display string.
        plant_species_id: Primary plant track.
        herbivore_species_id: Primary herbivore track.
        flora_ids: Specific flora entities.
        herbivore_ids: Specific herbivore entities.
        title: Display caption.
        x_label: Abscissa.
        y_label: Ordinate.
        x_max: Boundary dimension.
        y_max: Boundary dimension.

    Returns:
        The operation status alongside a Base64-encoded PNG string.
    """
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
