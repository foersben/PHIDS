"""Academic export pipeline for PHIDS telemetry data.

This module implements the export layer that transforms Polars DataFrames produced by
:class:`~phids.telemetry.analytics.TelemetryRecorder` into publication-ready artifacts
suitable for peer-reviewed manuscript submission. Four output formats are supported:

1. **CSV** — Plain-text comma-separated values compatible with spreadsheet tools and
   statistical computing environments.
2. **NDJSON** — Newline-delimited JSON for programmatic ingestion.
3. **PNG** — Rasterized chart rendered via ``matplotlib`` using the ``Agg`` (headless)
   backend, supporting both time-series and Lotka-Volterra phase-space views.
4. **PGFPlots TikZ** — LaTeX ``pgfplots`` source code generated from matplotlib figures
   via the ``pgf`` backend or an internal template generator, enabling vector-quality
   figures with full typography control for publication workflows. Note that TikZ
   generation does not require a local LaTeX installation at the Python level; the
   returned string is intended to be compiled by the end user's LaTeX toolchain.
5. **LaTeX Table** — A ``\\begin{tabular}`` environment generated via ``pandas.DataFrame.to_latex``
   with ``booktabs`` formatting (``\\toprule``, ``\\midrule``, ``\\bottomrule``), suitable
   for direct inclusion in manuscripts.

Per-species flattening is performed by :func:`telemetry_to_dataframe`, which converts the
nested per-species dicts stored in :attr:`TelemetryRecorder._rows` into a wide-format
pandas DataFrame with columns named ``plant_{id}_pop``, ``plant_{id}_energy``,
``swarm_{id}_pop``, and ``defense_cost_{id}``. This columnar layout is compatible with
both the matplotlib plotting functions and the LaTeX table generator.

The ``matplotlib.use("Agg")`` call is scoped to the function body (not the module level)
to avoid conflicting with interactive display backends in notebook or GUI contexts.
"""

from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

import polars as pl

if TYPE_CHECKING:
    import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Palette for per-species Chart.js / matplotlib series
# ---------------------------------------------------------------------------
_FLORA_COLOURS = ["#22c55e", "#84cc16", "#10b981", "#4ade80", "#a3e635"]
_PREDATOR_COLOURS = ["#ef4444", "#f97316", "#ec4899", "#f43f5e", "#fb923c"]


def _append_species_id(csv_ids: str | None, species_id: int) -> str:
    """Return a comma-delimited id list that contains ``species_id``.

    Args:
        csv_ids: Existing CSV id list or ``None``.
        species_id: Species identifier that must be present.

    Returns:
        str: Normalized CSV list including ``species_id``.
    """
    ids = _parse_species_ids(csv_ids) or set()
    ids.add(int(species_id))
    return ",".join(str(i) for i in sorted(ids))


def decimate_dataframe(df: "pd.DataFrame", tick_interval: int) -> "pd.DataFrame":
    """Return a tick-decimated DataFrame using stride semantics.

    Args:
        df: Input DataFrame.
        tick_interval: Row stride; values below 1 are treated as 1.

    Returns:
        pd.DataFrame: Decimated DataFrame.
    """
    stride = max(1, int(tick_interval))
    if stride <= 1 or df.empty:
        return df
    return df.iloc[::stride, :]


def _parse_species_ids(raw: str | None) -> set[int] | None:
    """Parse a comma-delimited species-id string into an integer set.

    Args:
        raw: Comma-delimited string (for example ``"0,2,4"``) or ``None``.

    Returns:
        Optional set[int]: Parsed ids; ``None`` when input is empty.
    """
    if raw is None or raw.strip() == "":
        return None
    out: set[int] = set()
    for token in raw.split(","):
        token = token.strip()
        if token == "":
            continue
        try:
            out.add(int(token))
        except ValueError:
            continue
    return out if out else None


def filter_telemetry_rows(
    rows: list[dict[str, Any]],
    *,
    flora_ids: str | None = None,
    predator_ids: str | None = None,
) -> list[dict[str, Any]]:
    """Filter per-species nested telemetry dictionaries by id.

    Args:
        rows: Raw telemetry rows.
        flora_ids: Optional CSV flora species-id list.
        predator_ids: Optional CSV predator species-id list.

    Returns:
        list[dict[str, Any]]: Row list with filtered species dictionaries.
    """
    flora_keep = _parse_species_ids(flora_ids)
    predator_keep = _parse_species_ids(predator_ids)
    if flora_keep is None and predator_keep is None:
        return rows

    filtered: list[dict[str, Any]] = []
    for row in rows:
        clone = dict(row)
        if flora_keep is not None:
            clone["plant_pop_by_species"] = {
                sid: val
                for sid, val in row.get("plant_pop_by_species", {}).items()
                if int(sid) in flora_keep
            }
            clone["plant_energy_by_species"] = {
                sid: val
                for sid, val in row.get("plant_energy_by_species", {}).items()
                if int(sid) in flora_keep
            }
            clone["defense_cost_by_species"] = {
                sid: val
                for sid, val in row.get("defense_cost_by_species", {}).items()
                if int(sid) in flora_keep
            }
        if predator_keep is not None:
            clone["swarm_pop_by_species"] = {
                sid: val
                for sid, val in row.get("swarm_pop_by_species", {}).items()
                if int(sid) in predator_keep
            }
        filtered.append(clone)
    return filtered


def filter_dataframe_columns(df: "pd.DataFrame", columns: str | None) -> "pd.DataFrame":
    """Return a DataFrame restricted to requested columns.

    Args:
        df: Input pandas DataFrame.
        columns: Optional CSV column list.

    Returns:
        pd.DataFrame: Filtered DataFrame containing only existing columns.
    """
    if columns is None or columns.strip() == "" or df.empty:
        return df
    wanted = [c.strip() for c in columns.split(",") if c.strip()]
    if "tick" not in wanted and "tick" in df.columns:
        wanted.insert(0, "tick")
    kept = [c for c in wanted if c in df.columns]
    return df.loc[:, kept] if kept else df


# ---------------------------------------------------------------------------
# Low-level Polars helpers (no external deps)
# ---------------------------------------------------------------------------


def export_csv(df: pl.DataFrame, path: str | Path) -> None:
    """Write the telemetry DataFrame to a CSV file.

    Args:
        df: Polars DataFrame produced by the telemetry recorder.
        path: Destination file path.
    """
    df.write_csv(str(path))


def export_json(df: pl.DataFrame, path: str | Path) -> None:
    """Write the telemetry DataFrame to a newline-delimited JSON file.

    Args:
        df: Polars DataFrame produced by the telemetry recorder.
        path: Destination file path.
    """
    df.write_ndjson(str(path))


def export_bytes_csv(df: pl.DataFrame) -> bytes:
    """Return the telemetry DataFrame serialized as CSV bytes.

    Args:
        df: Polars DataFrame to serialize.

    Returns:
        bytes: CSV-encoded bytes.
    """
    return df.write_csv().encode()


def export_bytes_json(df: pl.DataFrame) -> bytes:
    """Return the telemetry DataFrame serialized as NDJSON bytes.

    Args:
        df: Polars DataFrame to serialize.

    Returns:
        bytes: NDJSON-encoded bytes.
    """
    return df.write_ndjson().encode()


# ---------------------------------------------------------------------------
# Per-species flattening — Polars rows → wide pandas DataFrame
# ---------------------------------------------------------------------------


def telemetry_to_dataframe(rows: list[dict[str, Any]]) -> "pd.DataFrame":
    """Flatten per-species nested dicts from raw telemetry rows into a pandas DataFrame.

    Converts the list of row dicts accumulated by
    :class:`~phids.telemetry.analytics.TelemetryRecorder` into a wide-format
    pandas DataFrame. Each per-species nested dictionary (``plant_pop_by_species``,
    ``plant_energy_by_species``, ``swarm_pop_by_species``, ``defense_cost_by_species``)
    is exploded into individual columns named ``plant_{id}_pop``, ``plant_{id}_energy``,
    ``swarm_{id}_pop``, and ``defense_cost_{id}`` respectively. Missing species in a
    given tick are filled with zero, ensuring a fully rectangular output suitable for
    vectorised statistical operations and LaTeX table generation.

    Args:
        rows: Raw row list from ``TelemetryRecorder._rows``.

    Returns:
        pd.DataFrame: Wide-format DataFrame with one row per tick and one column per
        scalar metric or per-species measurement.
    """
    import pandas as pd  # local import to keep dependency optional at module load

    if not rows:
        return pd.DataFrame()

    # Collect all species ids seen across all rows
    all_flora_ids: set[int] = set()
    all_swarm_ids: set[int] = set()
    for row in rows:
        all_flora_ids.update(row.get("plant_pop_by_species", {}).keys())
        all_swarm_ids.update(row.get("swarm_pop_by_species", {}).keys())

    flat_rows = []
    for row in rows:
        flat: dict[str, Any] = {
            k: v for k, v in row.items() if not isinstance(v, dict)
        }
        pop_by = row.get("plant_pop_by_species", {})
        energy_by = row.get("plant_energy_by_species", {})
        swarm_by = row.get("swarm_pop_by_species", {})
        defense_by = row.get("defense_cost_by_species", {})

        for fid in sorted(all_flora_ids):
            flat[f"plant_{fid}_pop"] = pop_by.get(fid, 0)
            flat[f"plant_{fid}_energy"] = energy_by.get(fid, 0.0)
            flat[f"defense_cost_{fid}"] = defense_by.get(fid, 0.0)

        for sid in sorted(all_swarm_ids):
            flat[f"swarm_{sid}_pop"] = swarm_by.get(sid, 0)

        flat_rows.append(flat)

    logger.debug(
        "telemetry_to_dataframe: %d rows, %d flora species, %d predator species",
        len(rows), len(all_flora_ids), len(all_swarm_ids),
    )
    return pd.DataFrame(flat_rows)


# ---------------------------------------------------------------------------
# PNG export via matplotlib (headless Agg backend)
# ---------------------------------------------------------------------------


def generate_png_bytes(
    rows: list[dict[str, Any]],
    plot_type: str = "timeseries",
    *,
    flora_names: dict[int, str] | None = None,
    predator_names: dict[int, str] | None = None,
    prey_species_id: int = 0,
    predator_species_id: int = 0,
    include_flora_ids: str | None = None,
    include_predator_ids: str | None = None,
    title: str | None = None,
    x_label: str | None = None,
    y_label: str | None = None,
    x_max: float | None = None,
    y_max: float | None = None,
    dpi: int = 150,
) -> bytes:
    """Render a matplotlib chart to PNG bytes using the headless Agg backend.

    Supports five ``plot_type`` modes:

    * ``"timeseries"`` — Overlaid line chart with one series per flora and predator
      species, sharing a common tick x-axis and a left y-axis for population counts.
      Total flora energy is plotted on a secondary y-axis.
    * ``"phasespace"`` — Lotka-Volterra phase-space scatter with ``showLine=True``
      semantics, plotting the aggregate population of ``prey_species_id`` flora on
      the x-axis and the aggregate population of ``predator_species_id`` herbivores
      on the y-axis as a connected trajectory through time, revealing orbital cycles.
    * ``"defense_economy"`` — Per-species ratio of defense maintenance cost to
      per-species stored plant energy.
    * ``"biomass_stack"`` — Stacked area chart of per-species flora population,
      used as a biomass proxy under fixed-cell carrying-capacity constraints.
    * ``"survival_probability"`` — Per-tick percentage of runs remaining alive.

    The ``matplotlib.use("Agg")`` backend directive is applied locally before any
    pyplot call to prevent interference with interactive display backends.

    Args:
        rows: Raw telemetry rows from ``TelemetryRecorder._rows``.
        plot_type: Chart mode — ``"timeseries"``, ``"phasespace"``,
            ``"defense_economy"``, ``"biomass_stack"``, or
            ``"survival_probability"``.
        flora_names: Optional display names keyed by flora species id.
        predator_names: Optional display names keyed by predator species id.
        prey_species_id: Flora species id for phase-space x-axis.
        predator_species_id: Predator species id for phase-space y-axis.
        dpi: Output resolution in dots per inch.

    Returns:
        bytes: PNG-encoded figure bytes.

    Raises:
        ValueError: If ``plot_type`` is not a supported chart mode.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    flora_filter = include_flora_ids
    predator_filter = include_predator_ids
    if plot_type == "phasespace":
        flora_filter = _append_species_id(flora_filter, prey_species_id)
        predator_filter = _append_species_id(predator_filter, predator_species_id)
    plot_rows = filter_telemetry_rows(rows, flora_ids=flora_filter, predator_ids=predator_filter)
    fig, ax = plt.subplots(figsize=(10, 5), dpi=dpi)

    if not plot_rows:
        ax.text(0.5, 0.5, "No telemetry data", ha="center", va="center", transform=ax.transAxes)
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight", facecolor="white")
        plt.close(fig)
        return buf.getvalue()

    ticks = [r["tick"] for r in plot_rows]

    if plot_type == "timeseries":
        _plot_timeseries(
            ax,
            plot_rows,
            ticks,
            flora_names=flora_names,
            predator_names=predator_names,
            title=title,
            x_label=x_label,
            y_label=y_label,
        )
    elif plot_type == "phasespace":
        _plot_phasespace(
            ax,
            plot_rows,
            prey_species_id=prey_species_id,
            predator_species_id=predator_species_id,
            flora_names=flora_names,
            predator_names=predator_names,
            title=title,
            x_label=x_label,
            y_label=y_label,
            x_max=x_max,
            y_max=y_max,
        )
    elif plot_type == "defense_economy":
        _plot_defense_economy(
            ax,
            plot_rows,
            ticks,
            flora_names=flora_names,
            title=title,
            x_label=x_label,
            y_label=y_label,
        )
    elif plot_type == "biomass_stack":
        _plot_biomass_stack(
            ax,
            plot_rows,
            ticks,
            flora_names=flora_names,
            title=title,
            x_label=x_label,
            y_label=y_label,
        )
    elif plot_type == "survival_probability":
        _plot_survival_probability(
            ax,
            plot_rows,
            ticks,
            title=title,
            x_label=x_label,
            y_label=y_label,
        )
    else:
        plt.close(fig)
        raise ValueError(
            (
                f"Unknown plot_type '{plot_type}'; expected timeseries, phasespace, "
                "defense_economy, biomass_stack, or survival_probability"
            )
        )

    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    logger.debug("PNG export complete (plot_type=%s, dpi=%d, bytes=%d)", plot_type, dpi, buf.tell())
    return buf.getvalue()


def _plot_timeseries(
    ax: Any,
    rows: list[dict[str, Any]],
    ticks: list[int],
    *,
    flora_names: dict[int, str] | None,
    predator_names: dict[int, str] | None,
    title: str | None,
    x_label: str | None,
    y_label: str | None,
) -> None:
    """Render per-species population time series onto ``ax``.

    Args:
        ax: Matplotlib Axes instance.
        rows: Raw telemetry rows.
        ticks: Tick index list aligned with ``rows``.
        flora_names: Optional display names for flora species.
        predator_names: Optional display names for predator species.
    """
    all_flora: set[int] = set()
    all_pred: set[int] = set()
    for r in rows:
        all_flora.update(r.get("plant_pop_by_species", {}).keys())
        all_pred.update(r.get("swarm_pop_by_species", {}).keys())

    for i, fid in enumerate(sorted(all_flora)):
        colour = _FLORA_COLOURS[i % len(_FLORA_COLOURS)]
        name = (flora_names or {}).get(fid, f"Flora {fid}")
        y = [r.get("plant_pop_by_species", {}).get(fid, 0) for r in rows]
        ax.plot(ticks, y, color=colour, linewidth=1.5, label=name)

    for i, pid in enumerate(sorted(all_pred)):
        colour = _PREDATOR_COLOURS[i % len(_PREDATOR_COLOURS)]
        name = (predator_names or {}).get(pid, f"Predator {pid}")
        y = [r.get("swarm_pop_by_species", {}).get(pid, 0) for r in rows]
        ax.plot(ticks, y, color=colour, linewidth=1.5, linestyle="--", label=name)

    ax.set_xlabel(x_label or "Tick")
    ax.set_ylabel(y_label or "Population")
    ax.set_title(title or "PHIDS - Population Time Series")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)


def _plot_phasespace(
    ax: Any,
    rows: list[dict[str, Any]],
    *,
    prey_species_id: int,
    predator_species_id: int,
    flora_names: dict[int, str] | None,
    predator_names: dict[int, str] | None,
    title: str | None,
    x_label: str | None,
    y_label: str | None,
    x_max: float | None,
    y_max: float | None,
) -> None:
    """Render a Lotka-Volterra phase-space trajectory onto ``ax``.

    Args:
        ax: Matplotlib Axes instance.
        rows: Raw telemetry rows.
        prey_species_id: Flora species id to use as x-axis.
        predator_species_id: Predator species id to use as y-axis.
        flora_names: Optional display names for flora species.
        predator_names: Optional display names for predator species.
    """
    x = [r.get("plant_pop_by_species", {}).get(prey_species_id, 0) for r in rows]
    y = [r.get("swarm_pop_by_species", {}).get(predator_species_id, 0) for r in rows]

    prey_name = (flora_names or {}).get(prey_species_id, f"Flora {prey_species_id}")
    pred_name = (predator_names or {}).get(predator_species_id, f"Predator {predator_species_id}")

    n = len(x)
    if n > 0:
        colours = [float(i) / max(n - 1, 1) for i in range(n)]
        ax.scatter(x, y, c=colours, cmap="viridis", s=10, zorder=3, alpha=0.8)
        ax.plot(x, y, color="#64748b", linewidth=0.8, alpha=0.5, zorder=2)
        ax.plot(x[0], y[0], "go", markersize=8, label="Start", zorder=4)
        ax.plot(x[-1], y[-1], "rs", markersize=8, label="End", zorder=4)

    ax.set_xlabel(x_label or f"Population - {prey_name}")
    ax.set_ylabel(y_label or f"Population - {pred_name}")
    ax.set_title(title or "PHIDS - Lotka-Volterra Phase Space")
    if x_max is not None and x_max > 0:
        ax.set_xlim(0, float(x_max))
    if y_max is not None and y_max > 0:
        ax.set_ylim(0, float(y_max))
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)


def _plot_defense_economy(
    ax: Any,
    rows: list[dict[str, Any]],
    ticks: list[int],
    *,
    flora_names: dict[int, str] | None,
    title: str | None,
    x_label: str | None,
    y_label: str | None,
) -> None:
    """Render per-species defense-cost to energy ratio trajectories onto ``ax``.

    Args:
        ax: Matplotlib Axes instance.
        rows: Raw telemetry rows.
        ticks: Tick index list aligned with ``rows``.
        flora_names: Optional display names for flora species.
        title: Optional chart title override.
        x_label: Optional x-axis label override.
        y_label: Optional y-axis label override.
    """
    all_flora: set[int] = set()
    for r in rows:
        all_flora.update(r.get("plant_energy_by_species", {}).keys())
        all_flora.update(r.get("defense_cost_by_species", {}).keys())

    for i, fid in enumerate(sorted(all_flora)):
        colour = _FLORA_COLOURS[i % len(_FLORA_COLOURS)]
        name = (flora_names or {}).get(fid, f"Flora {fid}")
        ratio: list[float] = []
        for r in rows:
            defense = float(r.get("defense_cost_by_species", {}).get(fid, 0.0))
            energy = float(r.get("plant_energy_by_species", {}).get(fid, 0.0))
            ratio.append(defense / energy if energy > 0.0 else 0.0)
        ax.plot(ticks, ratio, color=colour, linewidth=1.5, label=name)

    ax.set_xlabel(x_label or "Tick")
    ax.set_ylabel(y_label or "Defense economy ratio")
    ax.set_title(title or "PHIDS - Metabolic Defense Economy")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)


def _plot_biomass_stack(
    ax: Any,
    rows: list[dict[str, Any]],
    ticks: list[int],
    *,
    flora_names: dict[int, str] | None,
    title: str | None,
    x_label: str | None,
    y_label: str | None,
) -> None:
    """Render stacked flora population trajectories as a biomass-proxy area chart.

    Args:
        ax: Matplotlib Axes instance.
        rows: Raw telemetry rows.
        ticks: Tick index list aligned with ``rows``.
        flora_names: Optional display names for flora species.
        title: Optional chart title override.
        x_label: Optional x-axis label override.
        y_label: Optional y-axis label override.
    """
    all_flora: set[int] = set()
    for r in rows:
        all_flora.update(r.get("plant_pop_by_species", {}).keys())
    ordered = sorted(all_flora)
    if not ordered:
        ax.plot(ticks, [0.0] * len(ticks), color="#94a3b8", linewidth=1.0, label="No flora")
    else:
        ys = [[float(r.get("plant_pop_by_species", {}).get(fid, 0.0)) for r in rows] for fid in ordered]
        labels = [(flora_names or {}).get(fid, f"Flora {fid}") for fid in ordered]
        colours = [_FLORA_COLOURS[i % len(_FLORA_COLOURS)] for i, _ in enumerate(ordered)]
        ax.stackplot(ticks, ys, labels=labels, colors=colours, alpha=0.35)
        for i, series in enumerate(ys):
            ax.plot(ticks, series, color=colours[i], linewidth=0.9, alpha=0.7)

    ax.set_xlabel(x_label or "Tick")
    ax.set_ylabel(y_label or "Stacked biomass proxy")
    ax.set_title(title or "PHIDS - Systemic Carrying Capacity")
    ax.legend(fontsize=8, loc="upper left")
    ax.grid(True, alpha=0.3)


def _plot_survival_probability(
    ax: Any,
    rows: list[dict[str, Any]],
    ticks: list[int],
    *,
    title: str | None,
    x_label: str | None,
    y_label: str | None,
) -> None:
    """Render batch survival probability trajectory onto ``ax``.

    Args:
        ax: Matplotlib Axes instance.
        rows: Raw telemetry rows containing ``survival_probability``.
        ticks: Tick index list aligned with ``rows``.
        title: Optional chart title override.
        x_label: Optional x-axis label override.
        y_label: Optional y-axis label override.
    """
    y = [100.0 * float(r.get("survival_probability", 0.0)) for r in rows]
    ax.plot(ticks, y, color="#0ea5e9", linewidth=2.0, label="Survival probability")
    ax.fill_between(ticks, y, [0.0] * len(y), color="#0ea5e9", alpha=0.15)
    ax.set_xlabel(x_label or "Tick")
    ax.set_ylabel(y_label or "Simulations alive (%)")
    ax.set_title(title or "PHIDS - Batch Survival Probability")
    ax.set_ylim(0, 100)
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)


# ---------------------------------------------------------------------------
# PGFPlots / TikZ export (LaTeX-compilable, no tikzplotlib dependency)
# ---------------------------------------------------------------------------


def generate_tikz_str(
    rows: list[dict[str, Any]],
    plot_type: str = "timeseries",
    *,
    flora_names: dict[int, str] | None = None,
    predator_names: dict[int, str] | None = None,
    prey_species_id: int = 0,
    predator_species_id: int = 0,
    include_flora_ids: str | None = None,
    include_predator_ids: str | None = None,
    title: str | None = None,
    x_label: str | None = None,
    y_label: str | None = None,
    x_max: float | None = None,
    y_max: float | None = None,
) -> str:
    """Generate a PGFPlots LaTeX source string for publication-quality figures.

    Produces a self-contained ``tikzpicture`` environment using the ``pgfplots``
    package. The output does not require the ``tikzplotlib`` library; instead,
    coordinates are injected directly into ``\\addplot`` commands via a
    ``\\pgfplotstable``-compatible inline coordinate format. This approach ensures
    compatibility with any LaTeX installation providing ``pgfplots >= 1.16``.

    The generated code is intended for compilation with ``pdflatex``, ``xelatex``,
    or ``lualatex`` after pasting into a document preamble that includes
    ``\\usepackage{pgfplots}`` and ``\\pgfplotsset{compat=1.18}``.

    Args:
        rows: Raw telemetry rows from ``TelemetryRecorder._rows``.
        plot_type: Chart mode — ``"timeseries"``, ``"phasespace"``,
            ``"defense_economy"``, ``"biomass_stack"``, or
            ``"survival_probability"``.
        flora_names: Optional display names keyed by flora species id.
        predator_names: Optional display names keyed by predator species id.
        prey_species_id: Flora species id for phase-space x-axis.
        predator_species_id: Predator species id for phase-space y-axis.

    Returns:
        str: LaTeX source code for a complete ``tikzpicture`` environment.

    Raises:
        ValueError: If ``plot_type`` is not a supported chart mode.
    """
    flora_filter = include_flora_ids
    predator_filter = include_predator_ids
    if plot_type == "phasespace":
        flora_filter = _append_species_id(flora_filter, prey_species_id)
        predator_filter = _append_species_id(predator_filter, predator_species_id)
    plot_rows = filter_telemetry_rows(rows, flora_ids=flora_filter, predator_ids=predator_filter)
    if plot_type == "timeseries":
        return _tikz_timeseries(
            plot_rows,
            flora_names=flora_names,
            predator_names=predator_names,
            title=title,
            x_label=x_label,
            y_label=y_label,
        )
    if plot_type == "phasespace":
        return _tikz_phasespace(
            plot_rows,
            prey_species_id=prey_species_id,
            predator_species_id=predator_species_id,
            flora_names=flora_names,
            predator_names=predator_names,
            title=title,
            x_label=x_label,
            y_label=y_label,
            x_max=x_max,
            y_max=y_max,
        )
    if plot_type == "defense_economy":
        return _tikz_defense_economy(
            plot_rows,
            flora_names=flora_names,
            title=title,
            x_label=x_label,
            y_label=y_label,
        )
    if plot_type == "biomass_stack":
        return _tikz_biomass_stack(
            plot_rows,
            flora_names=flora_names,
            title=title,
            x_label=x_label,
            y_label=y_label,
        )
    if plot_type == "survival_probability":
        return _tikz_survival_probability(
            plot_rows,
            title=title,
            x_label=x_label,
            y_label=y_label,
        )
    raise ValueError(
        (
            f"Unknown plot_type '{plot_type}'; expected timeseries, phasespace, defense_economy, "
            "biomass_stack, or survival_probability"
        )
    )


def _tikz_timeseries(
    rows: list[dict[str, Any]],
    *,
    flora_names: dict[int, str] | None,
    predator_names: dict[int, str] | None,
    title: str | None,
    x_label: str | None,
    y_label: str | None,
) -> str:
    """Build PGFPlots code for a population time-series chart.

    Args:
        rows: Raw telemetry rows.
        flora_names: Optional display names for flora species.
        predator_names: Optional display names for predator species.

    Returns:
        str: LaTeX ``tikzpicture`` source.
    """
    all_flora: set[int] = set()
    all_pred: set[int] = set()
    for r in rows:
        all_flora.update(r.get("plant_pop_by_species", {}).keys())
        all_pred.update(r.get("swarm_pop_by_species", {}).keys())

    flora_colours = ["green!60!black", "lime!80!black", "teal", "green!40!black", "olive"]
    pred_colours = ["red!70!black", "orange!80!black", "magenta!60!black", "pink!60!black", "brown"]

    plots = []
    for i, fid in enumerate(sorted(all_flora)):
        colour = flora_colours[i % len(flora_colours)]
        name = (flora_names or {}).get(fid, f"Flora {fid}")
        coords = " ".join(
            f"({r['tick']},{r.get('plant_pop_by_species', {}).get(fid, 0)})" for r in rows
        )
        plots.append(
            f"    \\addplot[color={colour}, thick] coordinates {{{coords}}};\n"
            f"    \\addlegendentry{{{name}}}"
        )

    for i, pid in enumerate(sorted(all_pred)):
        colour = pred_colours[i % len(pred_colours)]
        name = (predator_names or {}).get(pid, f"Predator {pid}")
        coords = " ".join(
            f"({r['tick']},{r.get('swarm_pop_by_species', {}).get(pid, 0)})" for r in rows
        )
        plots.append(
            f"    \\addplot[color={colour}, thick, dashed] coordinates {{{coords}}};\n"
            f"    \\addlegendentry{{{name}}}"
        )

    body = "\n".join(plots)
    return (
        "\\begin{tikzpicture}\n"
        "\\begin{axis}[\n"
        f"    xlabel={{{x_label or 'Tick'}}},\n"
        f"    ylabel={{{y_label or 'Population'}}},\n"
        f"    title={{{title or 'PHIDS -- Population Time Series'}}},\n"
        "    legend pos=north east,\n"
        "    grid=major,\n"
        "    width=12cm, height=7cm,\n"
        "]\n"
        + body
        + "\n\\end{axis}\n\\end{tikzpicture}"
    )


def _tikz_phasespace(
    rows: list[dict[str, Any]],
    *,
    prey_species_id: int,
    predator_species_id: int,
    flora_names: dict[int, str] | None,
    predator_names: dict[int, str] | None,
    title: str | None,
    x_label: str | None,
    y_label: str | None,
    x_max: float | None,
    y_max: float | None,
) -> str:
    """Build PGFPlots code for a Lotka-Volterra phase-space chart.

    Args:
        rows: Raw telemetry rows.
        prey_species_id: Flora species id for x-axis.
        predator_species_id: Predator species id for y-axis.
        flora_names: Optional display names for flora species.
        predator_names: Optional display names for predator species.

    Returns:
        str: LaTeX ``tikzpicture`` source.
    """
    prey_name = (flora_names or {}).get(prey_species_id, f"Flora {prey_species_id}")
    pred_name = (predator_names or {}).get(predator_species_id, f"Predator {predator_species_id}")

    coords = " ".join(
        f"({r.get('plant_pop_by_species', {}).get(prey_species_id, 0)},"
        f"{r.get('swarm_pop_by_species', {}).get(predator_species_id, 0)})"
        for r in rows
    )

    x_bound = f"    xmax={float(x_max)},\n" if x_max is not None and x_max > 0 else ""
    y_bound = f"    ymax={float(y_max)},\n" if y_max is not None and y_max > 0 else ""

    return (
        "\\begin{tikzpicture}\n"
        "\\begin{axis}[\n"
        f"    xlabel={{{x_label or (prey_name + ' Population')}}},\n"
        f"    ylabel={{{y_label or (pred_name + ' Population')}}},\n"
        f"    title={{{title or 'PHIDS -- Lotka-Volterra Phase Space'}}},\n"
        + x_bound
        + y_bound
        + "    grid=major,\n"
        + "    width=10cm, height=10cm,\n"
        + "]\n"
        f"    \\addplot[color=violet!70!black, thick, mark=none] coordinates {{{coords}}};\n"
        "\\end{axis}\n\\end{tikzpicture}"
    )


def _tikz_defense_economy(
    rows: list[dict[str, Any]],
    *,
    flora_names: dict[int, str] | None,
    title: str | None,
    x_label: str | None,
    y_label: str | None,
) -> str:
    """Build PGFPlots code for per-species defense economy trajectories.

    Args:
        rows: Raw telemetry rows.
        flora_names: Optional display names for flora species.
        title: Optional chart title override.
        x_label: Optional x-axis label override.
        y_label: Optional y-axis label override.

    Returns:
        str: LaTeX ``tikzpicture`` source.
    """
    all_flora: set[int] = set()
    for r in rows:
        all_flora.update(r.get("plant_energy_by_species", {}).keys())
        all_flora.update(r.get("defense_cost_by_species", {}).keys())

    flora_colours = ["green!60!black", "lime!80!black", "teal", "green!40!black", "olive"]
    plots = []
    for i, fid in enumerate(sorted(all_flora)):
        colour = flora_colours[i % len(flora_colours)]
        name = (flora_names or {}).get(fid, f"Flora {fid}")
        coords_parts = []
        for r in rows:
            tick = r.get("tick", 0)
            defense = float(r.get("defense_cost_by_species", {}).get(fid, 0.0))
            energy = float(r.get("plant_energy_by_species", {}).get(fid, 0.0))
            ratio = defense / energy if energy > 0.0 else 0.0
            coords_parts.append(f"({tick},{ratio})")
        coords = " ".join(coords_parts)
        plots.append(
            f"    \\addplot[color={colour}, thick] coordinates {{{coords}}};\n"
            f"    \\addlegendentry{{{name}}}"
        )

    body = "\n".join(plots)
    return (
        "\\begin{tikzpicture}\n"
        "\\begin{axis}[\n"
        f"    xlabel={{{x_label or 'Tick'}}},\n"
        f"    ylabel={{{y_label or 'Defense economy ratio'}}},\n"
        f"    title={{{title or 'PHIDS -- Metabolic Defense Economy'}}},\n"
        "    legend pos=north east,\n"
        "    grid=major,\n"
        "    width=12cm, height=7cm,\n"
        "]\n"
        + body
        + "\n\\end{axis}\n\\end{tikzpicture}"
    )


def _tikz_biomass_stack(
    rows: list[dict[str, Any]],
    *,
    flora_names: dict[int, str] | None,
    title: str | None,
    x_label: str | None,
    y_label: str | None,
) -> str:
    """Build PGFPlots code for stacked-biomass proxy trajectories.

    Args:
        rows: Raw telemetry rows.
        flora_names: Optional display names for flora species.
        title: Optional chart title override.
        x_label: Optional x-axis label override.
        y_label: Optional y-axis label override.

    Returns:
        str: LaTeX ``tikzpicture`` source.
    """
    all_flora: set[int] = set()
    for r in rows:
        all_flora.update(r.get("plant_pop_by_species", {}).keys())

    flora_colours = ["green!60!black", "lime!80!black", "teal", "green!40!black", "olive"]
    plots = []
    for i, fid in enumerate(sorted(all_flora)):
        colour = flora_colours[i % len(flora_colours)]
        name = (flora_names or {}).get(fid, f"Flora {fid}")
        coords = " ".join(
            f"({r.get('tick', 0)},{r.get('plant_pop_by_species', {}).get(fid, 0)})" for r in rows
        )
        plots.append(
            f"    \\addplot+[name path={name.replace(' ', '_')}, color={colour}, thick] coordinates {{{coords}}};\n"
            f"    \\addlegendentry{{{name}}}"
        )

    body = "\n".join(plots)
    return (
        "\\begin{tikzpicture}\n"
        "\\begin{axis}[\n"
        f"    xlabel={{{x_label or 'Tick'}}},\n"
        f"    ylabel={{{y_label or 'Stacked biomass proxy'}}},\n"
        f"    title={{{title or 'PHIDS -- Systemic Carrying Capacity'}}},\n"
        "    legend pos=north east,\n"
        "    grid=major,\n"
        "    width=12cm, height=7cm,\n"
        "]\n"
        + body
        + "\n\\end{axis}\n\\end{tikzpicture}"
    )


def _tikz_survival_probability(
    rows: list[dict[str, Any]],
    *,
    title: str | None,
    x_label: str | None,
    y_label: str | None,
) -> str:
    """Build PGFPlots code for batch survival probability trajectories.

    Args:
        rows: Raw telemetry rows containing ``survival_probability``.
        title: Optional chart title override.
        x_label: Optional x-axis label override.
        y_label: Optional y-axis label override.

    Returns:
        str: LaTeX ``tikzpicture`` source.
    """
    coords = " ".join(
        f"({r.get('tick', 0)},{100.0 * float(r.get('survival_probability', 0.0))})" for r in rows
    )
    return (
        "\\begin{tikzpicture}\n"
        "\\begin{axis}[\n"
        f"    xlabel={{{x_label or 'Tick'}}},\n"
        f"    ylabel={{{y_label or 'Simulations alive (%)'}}},\n"
        f"    title={{{title or 'PHIDS -- Batch Survival Probability'}}},\n"
        "    ymin=0, ymax=100,\n"
        "    grid=major,\n"
        "    width=12cm, height=7cm,\n"
        "]\n"
        f"    \\addplot[color=cyan!70!black, thick] coordinates {{{coords}}};\n"
        "\\end{axis}\n\\end{tikzpicture}"
    )


# ---------------------------------------------------------------------------
# LaTeX table export via pandas
# ---------------------------------------------------------------------------


def export_bytes_tex_table(
    rows: list[dict[str, Any]],
    *,
    columns: str | None = None,
    include_flora_ids: str | None = None,
    include_predator_ids: str | None = None,
    tick_interval: int = 1,
) -> bytes:
    """Render the telemetry rows as a booktabs LaTeX tabular environment.

    Flattens per-species dicts into a wide pandas DataFrame via
    :func:`telemetry_to_dataframe`, then serialises to LaTeX using
    ``DataFrame.to_latex(index=False)``, which emits
    ``\\toprule``, ``\\midrule``, and ``\\bottomrule`` rules consistent with
    the ``booktabs`` LaTeX package conventions expected in peer-reviewed journals.

    Args:
        rows: Raw telemetry rows from ``TelemetryRecorder._rows``.

    Returns:
        bytes: UTF-8 encoded LaTeX ``tabular`` source.
    """
    filtered_rows = filter_telemetry_rows(rows, flora_ids=include_flora_ids, predator_ids=include_predator_ids)
    df = telemetry_to_dataframe(filtered_rows)
    df = filter_dataframe_columns(df, columns)
    df = decimate_dataframe(df, tick_interval)
    if df.empty:
        return b"% No telemetry data\n"
    latex: str = df.to_latex(index=False, float_format="%.2f")  # type: ignore[attr-defined]
    return latex.encode("utf-8")


# ---------------------------------------------------------------------------
# Batch aggregate export helpers
# ---------------------------------------------------------------------------


def aggregate_to_dataframe(
    aggregate: dict[str, Any],
    *,
    flora_names: dict[int, str] | None = None,
    predator_names: dict[int, str] | None = None,
) -> "pd.DataFrame":
    """Convert a batch aggregate summary dict to a wide pandas DataFrame.

    Constructs a per-tick DataFrame from the mean and standard deviation arrays
    stored inside the aggregate summary produced by
    :func:`~phids.engine.batch.aggregate_batch_telemetry`.

    Args:
        aggregate: Dict with keys ``ticks``, ``flora_population_mean``,
            ``flora_population_std``, ``predator_population_mean``,
            ``predator_population_std``, and optionally per-species series.
        flora_names: Optional display name mapping for flora species.
        predator_names: Optional display name mapping for predator species.

    Returns:
        pd.DataFrame: Wide-format DataFrame ready for export.
    """
    import pandas as pd

    ticks = aggregate.get("ticks", [])
    if not ticks:
        return pd.DataFrame()

    data: dict[str, Any] = {"tick": ticks}
    data["flora_population_mean"] = aggregate.get("flora_population_mean", [0.0] * len(ticks))
    data["flora_population_std"] = aggregate.get("flora_population_std", [0.0] * len(ticks))
    data["predator_population_mean"] = aggregate.get("predator_population_mean", [0.0] * len(ticks))
    data["predator_population_std"] = aggregate.get("predator_population_std", [0.0] * len(ticks))

    for fid, series_mean in aggregate.get("per_flora_pop_mean", {}).items():
        name = (flora_names or {}).get(int(fid), f"flora_{fid}")
        data[f"{name}_pop_mean"] = series_mean
        series_std = aggregate.get("per_flora_pop_std", {}).get(fid, [0.0] * len(ticks))
        data[f"{name}_pop_std"] = series_std

    for pid, series_mean in aggregate.get("per_predator_pop_mean", {}).items():
        name = (predator_names or {}).get(int(pid), f"predator_{pid}")
        data[f"{name}_pop_mean"] = series_mean
        series_std = aggregate.get("per_predator_pop_std", {}).get(pid, [0.0] * len(ticks))
        data[f"{name}_pop_std"] = series_std

    return pd.DataFrame(data)


