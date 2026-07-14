"""Pure structural utility helpers for the UI dashboard presenters.

Provides deterministic coercion, coordinate validation, and fallback rendering logic
used across multiple presenter domains (mycorrhizal, substances, cell details).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException

if TYPE_CHECKING:
    from collections.abc import Mapping


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
    for a UI tooltip or summary label.

    Args:
        condition: A dictionary conforming to the activation condition schema, or
            ``None`` to indicate unconditional activation.
        herbivore_names: Optional mapping from herbivore species identifier to display name.
            If omitted, fallback labels (e.g. ``"Herbivore 0"``) are used.
        substance_names: Optional mapping from substance identifier to display name.
            If omitted, fallback labels (e.g. ``"Signal 0"``) are used.

    Returns:
        A human-readable string summarizing the condition logic.

    """
    if condition is None:
        return "unconditional"

    if not condition:
        return "unconditional"

    h_names = herbivore_names or {}
    s_names = substance_names or {}

    kind = condition.get("kind")
    if kind == "herbivore_presence":
        sid = _coerce_int(condition.get("herbivore_species_id"))
        pop = _coerce_int(condition.get("min_herbivore_population"), default=1)
        name = h_names.get(sid, f"Herbivore {sid}")
        return f"{name} ≥ {pop}"
    if kind == "substance_active":
        sid = _coerce_int(condition.get("substance_id"))
        name = s_names.get(sid, _default_substance_name(sid, is_toxin=False))
        return f"{name} active"
    if kind == "environmental_signal":
        sid = _coerce_int(condition.get("signal_id"))
        thresh = _coerce_float(condition.get("min_concentration"))
        name = s_names.get(sid, _default_substance_name(sid, is_toxin=False))
        return f"{name} concentration ≥ {thresh}"
    if kind == "all_of":
        sub_conditions = condition.get("conditions", [])
        if not isinstance(sub_conditions, list):
            return "invalid condition"
        parts = [
            _describe_activation_condition(sub, herbivore_names=h_names, substance_names=s_names)
            for sub in sub_conditions
            if isinstance(sub, dict)
        ]
        return f"({' AND '.join(parts)})" if parts else "unconditional"
    if kind == "any_of":
        sub_conditions = condition.get("conditions", [])
        if not isinstance(sub_conditions, list):
            return "invalid condition"
        parts = [
            _describe_activation_condition(sub, herbivore_names=h_names, substance_names=s_names)
            for sub in sub_conditions
            if isinstance(sub, dict)
        ]
        return f"({' OR '.join(parts)})" if parts else "unconditional"

    return "unknown condition"


def validate_cell_coordinates(x: int, y: int, width: int, height: int) -> None:
    """Assert that a pair of cell coordinates falls within the simulation grid bounds.

    Args:
        x: Column index to validate.
        y: Row index to validate.
        width: Total grid width.
        height: Total grid height.

    Raises:
        HTTPException: Raises HTTP 404 with a descriptive detail message if the
            coordinates are out of bounds.

    """
    if not (0 <= x < width) or not (0 <= y < height):
        raise HTTPException(
            status_code=404,
            detail=f"Cell coordinates ({x}, {y}) out of bounds for grid {width}x{height}",
        )
