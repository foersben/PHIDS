"""Simulation status badge presenter."""

from phids.engine.loop import SimulationLoop


def render_status_badge_html(sim_loop: SimulationLoop | None) -> str:
    """Render the HTMX-polled simulation status badge fragment.

    Args:
        sim_loop: Active simulation loop instance, or None if draft mode.

    Returns:
        HTML fragment encoding current lifecycle state with semantic coloring.
    """
    if sim_loop is None:
        label, colour = "Idle", "bg-slate-100 text-slate-500"
    elif sim_loop.terminated:
        label, colour = "Terminated", "bg-red-100 text-red-600"
    elif sim_loop.paused:
        label, colour = "Paused", "bg-amber-100 text-amber-600"
    elif sim_loop.running:
        label, colour = "Running", "bg-emerald-100 text-emerald-600"
    else:
        label, colour = "Loaded", "bg-indigo-100 text-indigo-600"

    return (
        f'<span id="sim-status" style="display:none!important" '
        f'hx-get="/api/ui/status-badge" hx-trigger="every 2s" hx-swap="outerHTML" '
        f'class="text-xs px-2 py-1 rounded {colour}">{label}</span>'
    )
