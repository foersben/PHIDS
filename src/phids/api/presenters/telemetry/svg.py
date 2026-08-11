# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Telemetry SVG chart presenter.

Module-level memoization ensures that the SVG string is rebuilt at most once per simulation tick.
The cache key is ``(df.height, latest_tick)``: if the row count and the most recent tick value are
both unchanged between two consecutive HTMX polls, the cached string is returned immediately,
completely eliminating the Polars ``.to_list()`` extraction and string-builder overhead.

Test isolation is supported by :func:`_invalidate_svg_cache`, which resets the cache between test
runs without touching any production code paths.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Module-level cache state
# ---------------------------------------------------------------------------

_svg_cache_key: tuple[int, int] | None = None
_svg_cache_value: str | None = None

_EMPTY_SVG: str = (
    '<svg width="100%" height="80" viewBox="0 0 800 80">'
    '<text x="400" y="44" text-anchor="middle" fill="#94a3b8" font-size="13">'
    "No telemetry data yet."
    "</text></svg>"
)


def _invalidate_svg_cache() -> None:
    """Reset the module-level SVG memoization state.

    This function is a **test seam only**. Production code must never call it.
    Use it in ``pytest`` fixtures (``autouse=True``) to guarantee a clean cache
    state between test cases, preventing false-positive cache-hit assertions
    caused by test-order pollution of module-level globals in this module.
    """
    global _svg_cache_key, _svg_cache_value
    _svg_cache_key = None
    _svg_cache_value = None


# ---------------------------------------------------------------------------
# Internal rendering helper (pure, stateless - no cache interaction)
# ---------------------------------------------------------------------------


def _build_svg_uncached(ticks: list[int], flora_pop: list[int], herbivore_pop: list[int], flora_e: list[float]) -> str:
    """Render an SVG line chart from pre-extracted telemetry columns.

    This function is intentionally stateless and cache-free. It exists as a
    named helper so that tests can verify rendering correctness independently
    of the memoization layer in :func:`build_telemetry_svg`.

    Args:
        ticks: Ordered sequence of tick indices.
        flora_pop: Flora population counts aligned to ``ticks``.
        herbivore_pop: Herbivore population counts aligned to ``ticks``.
        flora_e: Aggregate flora energy values aligned to ``ticks``.

    Returns:
        SVG markup string suitable for ``innerHTML`` injection.
    """
    w, h, pad = 800, 160, 30

    max_tick = max(ticks) or 1
    max_pop = max(max(flora_pop, default=1), max(herbivore_pop, default=1)) or 1
    max_energy = max(flora_e, default=1.0) or 1.0

    def sx(t: int) -> float:
        return pad + (t / max_tick) * (w - 2 * pad)

    def sy_pop(v: int) -> float:
        return h - pad - (v / max_pop) * (h - 2 * pad)

    def sy_e(v: float) -> float:
        return h - pad - (v / max_energy) * (h - 2 * pad)

    n = len(ticks)
    fp_path = " ".join(f"{'M' if i == 0 else 'L'}{sx(ticks[i]):.1f},{sy_pop(flora_pop[i]):.1f}" for i in range(n))
    pp_path = " ".join(f"{'M' if i == 0 else 'L'}{sx(ticks[i]):.1f},{sy_pop(herbivore_pop[i]):.1f}" for i in range(n))
    fe_path = " ".join(f"{'M' if i == 0 else 'L'}{sx(ticks[i]):.1f},{sy_e(flora_e[i]):.1f}" for i in range(n))

    return (
        f'<svg width="100%" height="{h}" viewBox="0 0 {w} {h}" class="w-full">'
        f'<path d="{fp_path}" stroke="#22c55e" stroke-width="2" fill="none"/>'
        f'<path d="{pp_path}" stroke="#ef4444" stroke-width="2" fill="none"/>'
        f'<path d="{fe_path}" stroke="#60a5fa" stroke-width="1.5" fill="none" stroke-dasharray="4 2"/>'
        f"</svg>"
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_telemetry_svg(df: object) -> str:
    """Generate an inline SVG line chart from telemetry data, with memoization.

    The result is memoized at module level keyed on ``(df.height, latest_tick)``.
    Repeated calls with an unchanged dataframe (e.g., during a paused simulation)
    return the cached string immediately without re-running the Polars extraction
    or string-builder path.

    The cache is invalidated automatically when a new tick advances (``df.height``
    increases) or when the latest tick index changes. A simulation reset produces
    a new ``df.height = 1``, which also triggers a cache miss naturally.

    Args:
        df: Tabular telemetry object with columns ``tick``, ``flora_population``,
            ``herbivore_population``, ``total_flora_energy``.

    Returns:
        SVG markup suitable for ``innerHTML`` injection.

    Notes:
        The chart intentionally overlays flora population, herbivore population, and aggregate flora
        energy on a shared temporal axis to support rapid diagnosis of trophic oscillation and
        metabolic collapse onset.

        Call :func:`_invalidate_svg_cache` in test fixtures to reset module-level state between
        test cases.
    """
    global _svg_cache_key, _svg_cache_value

    import polars as pl

    if not isinstance(df, pl.DataFrame) or df.is_empty() or len(df) < 2:
        return _EMPTY_SVG

    latest_tick = int(df["tick"][-1])
    cache_key = (df.height, latest_tick)

    if cache_key == _svg_cache_key and _svg_cache_value is not None:
        return _svg_cache_value

    ticks: list[int] = df["tick"].to_list()
    flora_pop: list[int] = df["flora_population"].to_list()
    herbivore_pop: list[int] = df["herbivore_population"].to_list()
    flora_e: list[float] = df["total_flora_energy"].to_list()

    svg = _build_svg_uncached(ticks, flora_pop, herbivore_pop, flora_e)

    _svg_cache_key = cache_key
    _svg_cache_value = svg

    return svg
