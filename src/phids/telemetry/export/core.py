from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd

    from phids.telemetry.analytics import TelemetryRow

logger = logging.getLogger(__name__)

TelemetryRows = list["TelemetryRow"]

_FLORA_COLOURS = ["#22c55e", "#84cc16", "#10b981", "#4ade80", "#a3e635"]
_HERBIVORE_COLOURS = ["#ef4444", "#f97316", "#ec4899", "#f43f5e", "#fb923c"]


def _species_map(row: TelemetryRow, key: str) -> dict[int, object]:
    """Return a normalized integer-keyed species map for one telemetry row field."""
    raw = row.get(key, {})
    if not isinstance(raw, dict):
        return {}
    out: dict[int, object] = {}
    for sid, value in raw.items():
        try:
            sid_int = int(sid)
        except (TypeError, ValueError):
            continue
        out[sid_int] = value
    return out


def _to_int(value: object, default: int = 0) -> int:
    """Coerce heterogeneous scalar values to int with deterministic fallback."""
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default


def _object_mapping(value: object) -> Mapping[object, object]:
    """Return mapping view when the input is dictionary-like, otherwise empty mapping."""
    if isinstance(value, Mapping):
        return value
    return {}


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


def decimate_dataframe(df: pd.DataFrame, tick_interval: int) -> pd.DataFrame:
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
    rows: TelemetryRows,
    *,
    flora_ids: str | None = None,
    herbivore_ids: str | None = None,
) -> TelemetryRows:
    """Filter per-species nested telemetry dictionaries by id.

    Args:
        rows: Raw telemetry rows.
        flora_ids: Optional CSV flora species-id list.
        herbivore_ids: Optional CSV herbivore species-id list.

    Returns:
        TelemetryRows: Row list with filtered species dictionaries.
    """
    flora_keep = _parse_species_ids(flora_ids)
    herbivore_keep = _parse_species_ids(herbivore_ids)
    if flora_keep is None and herbivore_keep is None:
        return rows

    filtered: TelemetryRows = []
    for row in rows:
        clone = dict(row)
        plant_pop = _species_map(row, "plant_pop_by_species")
        plant_energy = _species_map(row, "plant_energy_by_species")
        defense_cost = _species_map(row, "defense_cost_by_species")
        swarm_pop = _species_map(row, "swarm_pop_by_species")
        if flora_keep is not None:
            clone["plant_pop_by_species"] = {sid: val for sid, val in plant_pop.items() if sid in flora_keep}
            clone["plant_energy_by_species"] = {sid: val for sid, val in plant_energy.items() if sid in flora_keep}
            clone["defense_cost_by_species"] = {sid: val for sid, val in defense_cost.items() if sid in flora_keep}
        if herbivore_keep is not None:
            clone["swarm_pop_by_species"] = {sid: val for sid, val in swarm_pop.items() if sid in herbivore_keep}
        filtered.append(clone)
    return filtered


def filter_dataframe_columns(df: pd.DataFrame, columns: str | None) -> pd.DataFrame:
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


def telemetry_to_dataframe(rows: TelemetryRows) -> pd.DataFrame:
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
        all_flora_ids.update(_species_map(row, "plant_pop_by_species").keys())
        all_swarm_ids.update(_species_map(row, "swarm_pop_by_species").keys())

    flat_rows = []
    for row in rows:
        flat: dict[str, object] = {k: v for k, v in row.items() if not isinstance(v, dict)}
        pop_by = _species_map(row, "plant_pop_by_species")
        energy_by = _species_map(row, "plant_energy_by_species")
        swarm_by = _species_map(row, "swarm_pop_by_species")
        defense_by = _species_map(row, "defense_cost_by_species")

        for fid in sorted(all_flora_ids):
            flat[f"plant_{fid}_pop"] = pop_by.get(fid, 0)
            flat[f"plant_{fid}_energy"] = energy_by.get(fid, 0.0)
            flat[f"defense_cost_{fid}"] = defense_by.get(fid, 0.0)

        for sid in sorted(all_swarm_ids):
            flat[f"swarm_{sid}_pop"] = swarm_by.get(sid, 0)

        flat_rows.append(flat)

    logger.debug(
        "telemetry_to_dataframe: %d rows, %d flora species, %d herbivore species",
        len(rows),
        len(all_flora_ids),
        len(all_swarm_ids),
    )
    return pd.DataFrame(flat_rows)


def aggregate_to_dataframe(
    aggregate: Mapping[str, object],
    *,
    flora_names: dict[int, str] | None = None,
    herbivore_names: dict[int, str] | None = None,
) -> pd.DataFrame:
    """Convert a batch aggregate summary dict to a wide pandas DataFrame.

    Constructs a per-tick DataFrame from the mean and standard deviation arrays
    stored inside the aggregate summary produced by
    :func:`~phids.engine.batch.aggregate_batch_telemetry`.

    Args:
        aggregate: Dict with keys ``ticks``, ``flora_population_mean``,
            ``flora_population_std``, ``herbivore_population_mean``,
            ``herbivore_population_std``, and optionally per-species series.
        flora_names: Optional display name mapping for flora species.
        herbivore_names: Optional display name mapping for herbivore species.

    Returns:
        pd.DataFrame: Wide-format DataFrame ready for export.
    """
    import pandas as pd

    ticks_raw = aggregate.get("ticks", [])
    if not isinstance(ticks_raw, list) or not ticks_raw:
        return pd.DataFrame()
    ticks: list[object] = ticks_raw

    data: dict[str, object] = {"tick": ticks}
    data["flora_population_mean"] = aggregate.get("flora_population_mean", [0.0] * len(ticks))
    data["flora_population_std"] = aggregate.get("flora_population_std", [0.0] * len(ticks))
    data["herbivore_population_mean"] = aggregate.get("herbivore_population_mean", [0.0] * len(ticks))
    data["herbivore_population_std"] = aggregate.get("herbivore_population_std", [0.0] * len(ticks))

    for fid, series_mean in _object_mapping(aggregate.get("per_flora_pop_mean", {})).items():
        fid_int = _to_int(fid, default=-1)
        name = (flora_names or {}).get(fid_int, f"flora_{fid_int}")
        data[f"{name}_pop_mean"] = series_mean
        series_std = _object_mapping(aggregate.get("per_flora_pop_std", {})).get(fid, [0.0] * len(ticks))
        data[f"{name}_pop_std"] = series_std

    for pid, series_mean in _object_mapping(aggregate.get("per_herbivore_pop_mean", {})).items():
        pid_int = _to_int(pid, default=-1)
        name = (herbivore_names or {}).get(pid_int, f"herbivore_{pid_int}")
        data[f"{name}_pop_mean"] = series_mean
        series_std = _object_mapping(aggregate.get("per_herbivore_pop_std", {})).get(pid, [0.0] * len(ticks))
        data[f"{name}_pop_std"] = series_std

    return pd.DataFrame(data)
