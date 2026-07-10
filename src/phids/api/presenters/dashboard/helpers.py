from __future__ import annotations

from collections.abc import Mapping

from fastapi import HTTPException


def _coerce_int(value: object, *, default: int = -1) -> int:
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


def _coerce_float(value: object, *, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return default
    return default


def _default_substance_name(substance_id: int, *, is_toxin: bool) -> str:
    return f"{'Toxin' if is_toxin else 'Signal'} {substance_id}"


def _describe_activation_condition(
    condition: Mapping[str, object] | None,
    *,
    herbivore_names: dict[int, str] | None = None,
    substance_names: dict[int, str] | None = None,
) -> str:
    if condition is None:
        return "unconditional"

    kind = condition.get("kind")
    if kind == "herbivore_presence":
        herbivore_species_id = _coerce_int(condition.get("herbivore_species_id", -1), default=-1)
        min_population = _coerce_int(condition.get("min_herbivore_population", 1), default=1)
        herbivore_label = (
            herbivore_names.get(herbivore_species_id, f"Herbivore {herbivore_species_id}")
            if herbivore_names is not None
            else f"Herbivore {herbivore_species_id}"
        )
        return f"{herbivore_label} ≥ {min_population}"
    if kind == "substance_active":
        substance_id = _coerce_int(condition.get("substance_id", -1), default=-1)
        substance_label = (
            substance_names.get(substance_id, _default_substance_name(substance_id, is_toxin=False))
            if substance_names is not None
            else _default_substance_name(substance_id, is_toxin=False)
        )
        return f"{substance_label} active"
    if kind == "environmental_signal":
        signal_id = _coerce_int(condition.get("signal_id", -1), default=-1)
        min_conc = _coerce_float(condition.get("min_concentration", 0.01), default=0.01)
        signal_label = (
            substance_names.get(signal_id, _default_substance_name(signal_id, is_toxin=False))
            if substance_names is not None
            else _default_substance_name(signal_id, is_toxin=False)
        )
        return f"{signal_label} concentration ≥ {min_conc:.2f}"

    raw_children = condition.get("conditions", [])
    if not isinstance(raw_children, list):
        return "unconditional"
    children = [child for child in raw_children if isinstance(child, Mapping)]
    joiner = " AND " if kind == "all_of" else " OR "
    if not children:
        return "unconditional"
    rendered = [
        _describe_activation_condition(child, herbivore_names=herbivore_names, substance_names=substance_names)
        for child in children
    ]
    return f"({joiner.join(rendered)})"


def validate_cell_coordinates(x: int, y: int, width: int, height: int) -> None:
    """Validate that (x, y) lies within the configured grid bounds.

    This guard is applied at the entry point of both live and draft cell-detail
    functions to ensure that coordinate lookups against NumPy environmental layers
    and the ECS spatial hash never produce out-of-bounds array accesses.

    Args:
        x: Column index of the target cell.
        y: Row index of the target cell.
        width: Total grid width in cells.
        height: Total grid height in cells.

    Raises:
        HTTPException: HTTP 404 if the coordinates fall outside ``[0, width) x [0, height)``.
    """
    if not (0 <= x < width and 0 <= y < height):
        raise HTTPException(
            status_code=404,
            detail=f"Cell ({x}, {y}) is outside the current {width}x{height} grid.",
        )
