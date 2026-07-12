"""Shared utility and data coercion functions for UI dashboards.

Provides pure-functional formatting, casting, and validation routines
that cross-cut specific presentation domains (like substances or mycorrhiza).
"""

from __future__ import annotations

from collections.abc import Mapping

from fastapi import HTTPException


def _coerce_int(value: object, *, default: int = -1) -> int:
    """Coerce an arbitrary object to ``int``, returning ``default`` on failure.

    Args:
        value: The input value to coerce.  Accepted types are ``int``, ``float``, and ``str``.
            ``bool`` values are explicitly rejected to avoid silent misinterpretation of flag
            fields as integer counts.
        default: Fallback integer returned when coercion is not possible.

    Returns:
        Coerced integer, or ``default`` if the input cannot be converted.
    """
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
    """Coerce an arbitrary object to ``float``, returning ``default`` on failure."""
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
    """Return a deterministic fallback display label for a substance identifier.

    The label encodes the biological classification (signal vs. toxin) and the integer
    identifier, ensuring operator-facing tooltips remain informative even when no explicit
    substance definition has been registered in the draft or live runtime.

    Args:
        substance_id: The integer substance channel index.
        is_toxin: Whether the substance occupies a toxin layer (``True``) or a signal layer
            (``False``).

    Returns:
        A human-readable label of the form ``"Toxin N"`` or ``"Signal N"``.
    """
    return f"{'Toxin' if is_toxin else 'Signal'} {substance_id}"


def _describe_activation_condition(
    condition: Mapping[str, object] | None,
    *,
    herbivore_names: dict[int, str] | None = None,
    substance_names: dict[int, str] | None = None,
) -> str:
    """Render a concise human-readable summary of a nested activation-condition tree.

    Activation conditions follow a recursive tree schema with leaf kinds
    ``herbivore_presence``, ``substance_active``, and ``environmental_signal``, and
    combinator kinds ``all_of`` and ``any_of``.  The function traverses the tree
    depth-first and assembles a parenthesised natural-language description suitable
    for operator-facing tooltips and the trigger-rules configuration panel.

    Args:
        condition: A deserialized condition node dictionary, or ``None`` for
            unconditional triggering.
        herbivore_names: Optional mapping from herbivore species identifier to display
            name.  Used to resolve ``herbivore_presence`` leaf labels.
        substance_names: Optional mapping from substance identifier to display name.
            Used to resolve ``substance_active`` and ``environmental_signal`` leaf labels.

    Returns:
        A human-readable condition summary string.  Returns ``"unconditional"`` when
        ``condition`` is ``None`` or when a combinator node has no valid children.
    """
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


# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
