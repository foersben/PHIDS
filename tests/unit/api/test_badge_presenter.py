# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Unit tests for the diagnostic badge presenter rendering functions."""

from unittest.mock import MagicMock

from phids.api.presenters.diagnostics.badge import render_main_action_btn_html, render_status_badge_html
from phids.engine.loop import SimulationLoop


def test_render_status_badge_html_none() -> None:
    """Verify status badge rendering when loop instance is None."""
    res = render_status_badge_html(None)
    assert "Idle" in res
    assert "bg-slate-100" in res


def test_render_status_badge_html_terminated() -> None:
    """Verify status badge rendering when simulation loop is terminated."""
    loop = MagicMock(spec=SimulationLoop)
    loop.terminated = True
    res = render_status_badge_html(loop)
    assert "Terminated" in res
    assert "bg-red-100" in res


def test_render_status_badge_html_paused() -> None:
    """Verify status badge rendering when simulation loop is paused."""
    loop = MagicMock(spec=SimulationLoop)
    loop.terminated = False
    loop.paused = True
    res = render_status_badge_html(loop)
    assert "Paused" in res
    assert "bg-amber-100" in res


def test_render_status_badge_html_running() -> None:
    """Verify status badge rendering when simulation loop is running."""
    loop = MagicMock(spec=SimulationLoop)
    loop.terminated = False
    loop.paused = False
    loop.running = True
    res = render_status_badge_html(loop)
    assert "Running" in res
    assert "bg-emerald-100" in res


def test_render_status_badge_html_loaded() -> None:
    """Verify status badge rendering when simulation loop is loaded but inactive."""
    loop = MagicMock(spec=SimulationLoop)
    loop.terminated = False
    loop.paused = False
    loop.running = False
    res = render_status_badge_html(loop)
    assert "Loaded" in res
    assert "bg-indigo-100" in res


def test_render_main_action_btn_html_none() -> None:
    """Verify main action button rendering when loop instance is None."""
    res = render_main_action_btn_html(None)
    assert "Start" in res
    assert "bg-emerald-500" in res


def test_render_main_action_btn_html_terminated() -> None:
    """Verify main action button rendering when simulation loop is terminated."""
    loop = MagicMock(spec=SimulationLoop)
    loop.terminated = True
    res = render_main_action_btn_html(loop)
    assert "Start" in res
    assert "bg-emerald-500" in res


def test_render_main_action_btn_html_paused() -> None:
    """Verify main action button rendering when simulation loop is paused."""
    loop = MagicMock(spec=SimulationLoop)
    loop.terminated = False
    loop.paused = True
    loop.running = False
    res = render_main_action_btn_html(loop)
    assert "Resume" in res
    assert "bg-indigo-500" in res


def test_render_main_action_btn_html_running() -> None:
    """Verify main action button rendering when simulation loop is actively running."""
    loop = MagicMock(spec=SimulationLoop)
    loop.terminated = False
    loop.paused = False
    loop.running = True
    res = render_main_action_btn_html(loop)
    assert "Pause" in res
    assert "bg-amber-500" in res
