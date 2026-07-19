"""Telemetry SVG chart presenter."""


def build_telemetry_svg(df: object) -> str:
    """Generate an inline SVG line chart from telemetry data.

    Args:
        df: Tabular telemetry object with columns ``tick``, ``flora_population``,
            ``herbivore_population``, ``total_flora_energy``.

    Returns:
        SVG markup suitable for ``innerHTML`` injection.

    Notes:
        The chart intentionally overlays flora population, herbivore population, and aggregate flora
        energy on a shared temporal axis to support rapid diagnosis of trophic oscillation and
        metabolic collapse onset.

    """
    import polars as pl

    if not isinstance(df, pl.DataFrame) or df.is_empty() or len(df) < 2:
        return (
            '<svg width="100%" height="80" viewBox="0 0 800 80">'
            '<text x="400" y="44" text-anchor="middle" fill="#94a3b8" font-size="13">'
            "No telemetry data yet."
            "</text></svg>"
        )

    w, h, pad = 800, 160, 30
    ticks: list[int] = df["tick"].to_list()
    flora_pop: list[int] = df["flora_population"].to_list()
    herbivore_pop: list[int] = df["herbivore_population"].to_list()
    flora_e: list[float] = df["total_flora_energy"].to_list()

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
