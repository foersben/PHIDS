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

    badge_html = (
        f'<span id="sim-status" style="display:none!important" '
        f'hx-get="/api/ui/status-badge" hx-trigger="every 2s, updateStatusBadge from:body" hx-swap="outerHTML" '
        f'class="text-xs px-2 py-1 rounded {colour}">{label}</span>'
    )
    return badge_html


def render_main_action_btn_html(sim_loop: SimulationLoop | None) -> str:
    """Render the main simulation action button (Play/Pause).

    Args:
        sim_loop: Active simulation loop instance, or None if draft mode.

    Returns:
        HTML fragment encoding current button state.
    """
    if sim_loop is None or sim_loop.terminated or (not sim_loop.running and not sim_loop.paused):
        btn_action, btn_text = "/api/simulation/start", "▶ Start"
        btn_color = "bg-emerald-500 hover:bg-emerald-600 focus-visible:ring-emerald-500"
    elif sim_loop.paused:
        btn_action, btn_text = "/api/simulation/start", "▶ Resume"
        btn_color = "bg-indigo-500 hover:bg-indigo-600 focus-visible:ring-indigo-500"
    else:
        btn_action, btn_text = "/api/simulation/pause", "⏸ Pause"
        btn_color = "bg-amber-500 hover:bg-amber-600 focus-visible:ring-amber-500"

    spinner_svg = (
        '<svg class="htmx-indicator absolute w-4 h-4 animate-spin opacity-0 transition-opacity '
        'duration-200 pointer-events-none" '
        'xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">'
        '<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>'
        '<path class="opacity-75" fill="currentColor" '
        'd="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 '
        '1.135 5.824 3 7.938l3-2.647z">'
        "</path></svg>"
    )

    btn_html = (
        f'<button id="sim-main-action-btn" '
        f'hx-post="{btn_action}" '
        f'hx-get="/api/ui/main-action-btn" '
        f'hx-trigger="updateMainActionBtn from:body" '
        f'hx-swap="outerHTML" '
        f'hx-include="#biotope-config-view form" '
        f'class="px-4 py-2 {btn_color} active:scale-95 active:brightness-90 focus:outline-none focus-visible:ring-2 '
        f"focus-visible:ring-offset-2 text-white rounded-lg text-sm font-medium transition-all shadow flex "
        f'items-center justify-center min-w-[5.5rem] relative">'
        f'<span class="btn-text transition-opacity duration-200">{btn_text}</span>'
        f"{spinner_svg}"
        f"</button>"
    )
    return btn_html
