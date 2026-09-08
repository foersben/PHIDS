"""Pure structural utility helpers for the UI dashboard presenters.

Provides deterministic coercion, coordinate validation, and fallback rendering logic
used across multiple presenter domains (mycorrhizal, substances, cell details).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException

if TYPE_CHECKING:
    from collections.abc import Mapping


from phids.shared.coercion import coerce_float, coerce_int


def _coerce_int(value: object, *, default: int = -1) -> int:
    """Coerce an arbitrary object to ``int``, returning ``default`` on failure or boolean input.

    In Python, ``bool`` is a subclass of ``int`` (e.g. ``isinstance(True, int) == True``).
    In dashboard presenters, accepting boolean inputs as integers would silently convert UI toggle
    flags (such as ``active=True``) into numeric entity identifiers (``species_id=1``) or cell
    coordinates (``x=0``). This function explicitly rejects boolean values, mapping them to
    ``default``, while safely parsing numbers and numeric strings.

    Args:
        value: The raw input object to convert (e.g. int, float, str, or None).
        default: Fallback integer returned if conversion fails or value is a boolean.
            Defaults to -1.

    Returns:
        int: The successfully coerced integer, or ``default`` if the input is invalid or boolean.

    Examples:
        >>> _coerce_int("42")
        42
        >>> _coerce_int(3.14)
        3
        >>> _coerce_int(True, default=-1)
        -1
        >>> _coerce_int("invalid", default=0)
        0
    """
    if isinstance(value, bool):
        return default
    return coerce_int(value, default=default)


def _coerce_float(value: object, *, default: float = 0.0) -> float:
    """Coerce an arbitrary object to ``float``, returning ``default`` on failure or boolean input.

    Similar to :func:`_coerce_int`, presenter layers explicitly reject boolean values to prevent
    UI flags from silently mutating continuous biological measurements (e.g. chemical concentrations
    or energy levels). Valid floats, integers, and numeric strings are parsed with strict fallbacks.

    Args:
        value: The raw input object to convert (e.g. float, int, str, or None).
        default: Fallback float returned if conversion fails or value is a boolean.
            Defaults to 0.0.

    Returns:
        float: The successfully coerced float, or ``default`` if the input is invalid or boolean.

    Examples:
        >>> _coerce_float("2.718")
        2.718
        >>> _coerce_float(10)
        10.0
        >>> _coerce_float(False, default=3.5)
        3.5
        >>> _coerce_float(None, default=0.0)
        0.0
    """
    if isinstance(value, bool):
        return default
    return coerce_float(value, default=default)


def calculate_structural_fragility_and_risk(
    struct_mass: float,
    max_struct: float,
) -> tuple[float, float, str]:
    """Compute biomass structural fragility and qualitative herbivory risk level.

    Calculates the proportional structural deficit of a plant relative to its maximum
    allometric structural capacity, translating it into an intuitive risk category:
    - "Immune": Structural mass has reached or exceeded maximum allometric capacity.
    - "High Risk": Fragility > 0.6 (severe structural deficit, highly vulnerable).
    - "Medium Risk": Fragility > 0.2 (moderate structural deficit).
    - "Low Risk": Fragility <= 0.2 (well-developed structural tissues).

    Args:
        struct_mass: The current structural mass of the plant in kilograms.
        max_struct: The maximum allometric structural capacity of the plant in kilograms.

    Returns:
        tuple[float, float, str]: A 3-tuple containing:
            - fragility: Normalized deficit in [0.0, 1.0].
            - fragility_pct: Percentage deficit in [0.0, 100.0].
            - risk_level: Categorical risk description ("Immune", "High Risk", "Medium Risk", "Low Risk").
    """
    struct_ratio = struct_mass / max_struct if max_struct > 0.0 else 0.0
    fragility = max(0.0, 1.0 - struct_ratio) if max_struct > 0.0 else 1.0
    fragility_pct = min(100.0, max(0.0, fragility * 100.0))

    if max_struct > 0.0 and struct_mass >= max_struct:
        risk_level = "Immune"
    elif fragility > 0.6:
        risk_level = "High Risk"
    elif fragility > 0.2:
        risk_level = "Medium Risk"
    else:
        risk_level = "Low Risk"

    return fragility, fragility_pct, risk_level


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


def _describe_composite_condition(
    condition: Mapping[str, object],
    joiner: str,
    h_names: dict[int, str],
    s_names: dict[int, str],
) -> str:
    """Recursively format composite activation conditions (all_of / any_of) into natural language.

    Args:
        condition: Mapping representing a composite condition node containing a "conditions" list.
        joiner: Infix separator string connecting child clauses (e.g. " AND " or " OR ").
        h_names: Mapping from herbivore species ID to human-readable display name.
        s_names: Mapping from substance ID to human-readable display name.

    Returns:
        str: Parenthesized natural-language description combining the child conditions,
            or a fallback indicator ("invalid condition" / "unconditional").
    """
    sub_conditions = condition.get("conditions", [])
    if not isinstance(sub_conditions, list):
        return "invalid condition"
    parts = [
        _describe_activation_condition(sub, herbivore_names=h_names, substance_names=s_names)
        for sub in sub_conditions
        if isinstance(sub, dict)
    ]
    return f"({joiner.join(parts)})" if parts else "unconditional"


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
        return _describe_composite_condition(condition, " AND ", h_names, s_names)
    if kind == "any_of":
        return _describe_composite_condition(condition, " OR ", h_names, s_names)

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
