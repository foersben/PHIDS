# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Telemetry inspection, schema query, and multi-format export tools for FastMCP."""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any, cast

from phids.mcp.app import mcp
from phids.mcp.helpers import get_active_sim_loop


@mcp.tool()
def inspect_telemetry_schema(zarr_store_path: str) -> dict[str, Any]:
    """Expose Zarr replay store structure to the agent without loading field arrays.

    Allows autonomous MLOps operators to inspect frame counts, top-level tree
    keys, and store-level metadata before initiating a heavy Polars lazy-frame
    extraction. The store is opened read-only; no data is mutated.

    Args:
        zarr_store_path: Filesystem path to a PHIDS ``.zarr`` replay store directory.

    Returns:
        dict[str, Any]: On success - ``status``, ``store_path``, ``frame_count``,
            ``tree_keys``, and ``store_attrs``. On failure - ``status`` and ``message``.
    """
    try:
        import numpy as np
        import zarr
    except ImportError as exc:  # pragma: no cover
        return {"status": "error", "message": f"Required package not available: {exc}"}

    store = Path(zarr_store_path)
    if not store.exists():
        return {
            "status": "error",
            "message": f"Store path does not exist: {zarr_store_path}",
        }

    try:
        root: zarr.Group = zarr.open_group(str(store), mode="r")
        tree_keys: list[str] = list(root.keys())

        frame_count: int = 0
        if "_metadata" in root:
            try:
                meta_node = cast("zarr.Array[Any]", root["_metadata"])
                meta_bytes = bytes(np.asarray(meta_node[:], dtype=np.uint8).tolist())
                meta_obj = json.loads(meta_bytes.decode("utf-8"))
                if isinstance(meta_obj, list):
                    frame_count = len(meta_obj)
                elif isinstance(meta_obj, dict) and "_metadata" in meta_obj:
                    inner = meta_obj["_metadata"]
                    frame_count = len(inner) if isinstance(inner, list) else 0
            except Exception:  # pragma: no cover
                frame_count = -1

        store_attrs: dict[str, Any] = dict(root.attrs) if root.attrs else {}

        return {
            "status": "success",
            "store_path": str(store.resolve()),
            "frame_count": frame_count,
            "tree_keys": tree_keys,
            "store_attrs": store_attrs,
        }
    except Exception as exc:
        return {"status": "error", "message": f"Failed to read Zarr store: {exc}"}


@mcp.tool()
def query_telemetry_schema() -> dict[str, Any]:
    """Return the available telemetry metrics for the active simulation.

    Agents can use this to determine which data columns are available to plot or export
    using the export_telemetry_data tool.

    Returns:
        dict[str, Any]: Available columns and structural layout.
    """
    loop = get_active_sim_loop()
    if loop is None:
        return {"status": "error", "message": "No active simulation loop loaded."}

    try:
        rows = loop.telemetry._rows
        if not rows:
            return {"status": "success", "columns": [], "message": "No telemetry recorded yet."}

        columns = list(rows[0].keys())
        return {"status": "success", "columns": columns}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def _export_csv_telemetry(
    filtered_rows: list[Any],
    normalized_data_type: str,
    tick_interval: int,
    columns: str | None,
) -> str:
    """Export filtered rows to CSV string format.

    Args:
        filtered_rows: Sequence of filtered telemetry rows.
        normalized_data_type: Chart or dataset type name.
        tick_interval: Stride interval for downsampling.
        columns: Optional comma-separated column filter string.

    Returns:
        str: Comma-separated tabular CSV string.
    """
    from phids.telemetry.export.core import (
        aggregate_to_dataframe,
        decimate_dataframe,
        filter_dataframe_columns,
        telemetry_to_dataframe,
    )

    if normalized_data_type in ("timeseries", "defense_economy", "biomass_stack"):
        df = aggregate_to_dataframe(filtered_rows)  # type: ignore[arg-type]
    else:
        df = telemetry_to_dataframe(filtered_rows)

    if tick_interval > 1:
        df = decimate_dataframe(df, tick_interval)

    if columns:
        df = filter_dataframe_columns(df, columns)

    return str(df.to_csv(index=False).encode("utf-8").decode("utf-8"))


def _export_tex_table_telemetry(
    rows: list[Any],
    columns: str | None,
    flora_ids: str | None,
    herbivore_ids: str | None,
    tick_interval: int,
) -> str:
    """Export telemetry rows to LaTeX booktabs tabular format.

    Args:
        rows: Sequence of telemetry rows.
        columns: Optional comma-separated column filter string.
        flora_ids: Optional comma-separated flora ID filter.
        herbivore_ids: Optional comma-separated herbivore ID filter.
        tick_interval: Stride interval for downsampling.

    Returns:
        str: LaTeX tabular snippet string.
    """
    from phids.telemetry.export.latex import export_bytes_tex_table

    bytes_data = export_bytes_tex_table(
        rows,
        columns=columns,
        include_flora_ids=flora_ids,
        include_herbivore_ids=herbivore_ids,
        tick_interval=tick_interval,
    )
    return bytes_data.decode("utf-8")


def _export_tex_tikz_telemetry(
    filtered_rows: list[Any],
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
) -> str:
    """Export filtered rows to PGFPlots TikZ code string.

    Args:
        filtered_rows: Sequence of filtered telemetry rows.
        normalized_data_type: Chart type identifier.
        flora_names: Mapping of flora ID to display name.
        herbivore_names: Mapping of herbivore ID to display name.
        plant_species_id: Flora ID for phase-space x-axis.
        herbivore_species_id: Herbivore ID for phase-space y-axis.
        flora_ids: Filter string for flora IDs.
        herbivore_ids: Filter string for herbivore IDs.
        title: Optional chart title.
        x_label: Optional x-axis label.
        y_label: Optional y-axis label.
        x_max: Optional x-axis scale maximum.
        y_max: Optional y-axis scale maximum.

    Returns:
        str: Self-contained PGFPlots TikZ figure code string.
    """
    from phids.telemetry.export.tikz import generate_tikz_str

    return generate_tikz_str(
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


def _export_png_telemetry(
    filtered_rows: list[Any],
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
) -> str:
    """Export filtered rows to base64-encoded PNG image string.

    Args:
        filtered_rows: Sequence of filtered telemetry rows.
        normalized_data_type: Chart type identifier.
        flora_names: Mapping of flora ID to display name.
        herbivore_names: Mapping of herbivore ID to display name.
        plant_species_id: Flora ID for phase-space x-axis.
        herbivore_species_id: Herbivore ID for phase-space y-axis.
        flora_ids: Filter string for flora IDs.
        herbivore_ids: Filter string for herbivore IDs.
        title: Optional chart title.
        x_label: Optional x-axis label.
        y_label: Optional y-axis label.
        x_max: Optional x-axis scale maximum.
        y_max: Optional y-axis scale maximum.

    Returns:
        str: Base64-encoded PNG image string.
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
    return base64.b64encode(bytes_data).decode("utf-8")


@mcp.tool()
def export_telemetry_data(
    format: str,
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
) -> dict[str, Any]:
    """Export telemetry from the active simulation as an encoded string.

    Generates academic telemetry exports (CSV, PNG, TikZ, LaTeX) mirroring
    the FastAPI endpoints but returning the payload directly for agent consumption.

    Args:
        format: 'csv', 'tex_table', 'tex_tikz', or 'png'.
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
        dict[str, Any]: A dictionary containing ``status``, ``format``, and ``data``.
            For binary formats (png), ``data`` is a base64 encoded string.
            For text formats (csv, tex_table, tex_tikz), ``data`` is a UTF-8 string.
    """
    loop = get_active_sim_loop()
    if loop is None:
        return {"status": "error", "message": "No active simulation loop loaded."}

    normalized_data_type = "defense_economy" if data_type == "metabolic" else data_type
    valid_data_types = {"timeseries", "phasespace", "defense_economy", "biomass_stack"}

    if normalized_data_type not in valid_data_types:
        return {"status": "error", "message": f"Invalid data_type. Must be one of {valid_data_types}"}

    if format not in {"csv", "tex_table", "tex_tikz", "png"}:
        return {"status": "error", "message": "Invalid format. Must be csv, tex_table, tex_tikz, or png."}

    try:
        from phids.telemetry.export.core import filter_telemetry_rows

        rows = loop.telemetry._rows
        flora_names = {sp.species_id: sp.name for sp in loop.config.flora_species}
        herbivore_names = {sp.species_id: sp.name for sp in loop.config.herbivore_species}

        filtered_rows = filter_telemetry_rows(rows, flora_ids=flora_ids, herbivore_ids=herbivore_ids)

        if format == "csv":
            data = _export_csv_telemetry(filtered_rows, normalized_data_type, tick_interval, columns)
        elif format == "tex_table":
            data = _export_tex_table_telemetry(rows, columns, flora_ids, herbivore_ids, tick_interval)
        elif format == "tex_tikz":
            data = _export_tex_tikz_telemetry(
                filtered_rows,
                normalized_data_type,
                flora_names,
                herbivore_names,
                plant_species_id,
                herbivore_species_id,
                flora_ids,
                herbivore_ids,
                title,
                x_label,
                y_label,
                x_max,
                y_max,
            )
        elif format == "png":
            data = _export_png_telemetry(
                filtered_rows,
                normalized_data_type,
                flora_names,
                herbivore_names,
                plant_species_id,
                herbivore_species_id,
                flora_ids,
                herbivore_ids,
                title,
                x_label,
                y_label,
                x_max,
                y_max,
            )
        else:
            return {"status": "error", "message": "Unknown format"}

        return {"status": "success", "format": format, "data": data}

    except Exception as e:
        return {"status": "error", "message": f"Export generation failed: {e}"}
