# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Experimental verification of WebSocket manager transport invariants.

This module evaluates the extracted connection managers that orchestrate PHIDS streaming transport.
The hypotheses test binary snapshot caching, deterministic close semantics, state-signature emission,
and disconnect resilience under asynchronous loop control. These checks validate that stream-layer
refactoring preserves stable observability of ecological state transitions while keeping transport
behavior explicit and bounded.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from fastapi import WebSocketDisconnect

from phids.api.websockets.manager import SimulationStreamManager, UIStreamManager


@dataclass(slots=True)
class _FakeConfig:
    """Minimal configuration surrogate exposing the stream-facing simulation contract."""

    tick_rate_hz: float = 10.0


class _FakeLock:
    """Minimal lock surrogate exposing the stream-facing simulation contract."""

    async def __aenter__(self):
        """Enter the context manager."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit the context manager."""
        pass


class _FakeLoop:
    """Minimal loop surrogate exposing the stream-facing simulation contract.

    Note that this is a pure mock used for testing the manager. It is NOT intended to be used for
    actual simulation execution.

    """

    def __init__(self, *, tick: int = 0, terminated: bool = False, tick_rate_hz: float = 10.0) -> None:
        """Initialize the fake loop.

        Args:
            tick: The initial tick number.
            terminated: Whether the loop is terminated.
            tick_rate_hz: The tick rate in Hz.
        """
        self.tick = tick
        self.state_revision = 0
        self.terminated = terminated
        self.running = False
        self.paused = False
        self.config = _FakeConfig(tick_rate_hz=tick_rate_hz)
        self.snapshot_calls = 0
        self._lock = _FakeLock()

    def get_state_snapshot(self) -> dict[str, int]:
        """Return deterministic snapshot payloads and count encoding requests.

        Returns:
            dict[str, int]: The snapshot payload.
        """
        self.snapshot_calls += 1
        return {"tick": self.tick}


class _FakeWebSocket:
    """Async WebSocket test double for manager-level transport tests.

    This test double exercises transport-layer failure modes (e.g. ``WebSocketDisconnect`` on send,
    ``RuntimeError`` on close) and records state change events for assertion.
    """

    def __init__(
        self,
        *,
        disconnect_on_send_bytes: bool = False,
        disconnect_on_send_text: bool = False,
        close_raises_runtime_error: bool = False,
    ) -> None:
        """Initialize the fake WebSocket.

        Args:
            disconnect_on_send_bytes: Whether to raise ``WebSocketDisconnect`` on ``send_bytes``.
            disconnect_on_send_text: Whether to raise ``WebSocketDisconnect`` on ``send_text``.
            close_raises_runtime_error: Whether to raise ``RuntimeError`` on ``close``.
        """
        self.disconnect_on_send_bytes = disconnect_on_send_bytes
        self.disconnect_on_send_text = disconnect_on_send_text
        self.close_raises_runtime_error = close_raises_runtime_error
        self.accepted = False
        self.closed: list[tuple[int, str | None]] = []
        self.sent_bytes: list[bytes] = []
        self.sent_text: list[str] = []

    async def accept(self) -> None:
        """Record connection acceptance."""
        self.accepted = True

    async def close(self, *, code: int = 1000, reason: str | None = None) -> None:
        """Record close events or emulate close-time runtime errors.

        Args:
            code: The close code.
            reason: The close reason.
        """
        if self.close_raises_runtime_error:
            raise RuntimeError("socket already closed")
        self.closed.append((code, reason))

    async def send_bytes(self, payload: bytes) -> None:
        """Record binary payloads or emulate client-initiated disconnects.

        Args:
            payload: The binary payload.
        """
        if self.disconnect_on_send_bytes:
            raise WebSocketDisconnect()
        self.sent_bytes.append(payload)

    async def send_text(self, payload: str) -> None:
        """Record text payloads or emulate client-initiated disconnects.

        Args:
            payload: The text payload.
        """
        if self.disconnect_on_send_text:
            raise WebSocketDisconnect()
        self.sent_text.append(payload)


@pytest.mark.asyncio
async def test_simulation_manager_reuses_snapshot_cache_for_unchanged_tick() -> None:
    """Verifies json+zlib cache reuse for repeated reads of one loop tick.

    The binary stream manager must avoid recompressing the same state payload while the simulation
    tick remains unchanged. This invariant minimizes transport overhead without altering the encoded
    ecological state.
    """
    manager = SimulationStreamManager()
    loop = _FakeLoop(tick=4)

    first_payload = manager._encoded_snapshot_bytes(loop)
    second_payload = manager._encoded_snapshot_bytes(loop)

    assert first_payload == second_payload
    assert loop.snapshot_calls == 1

    loop.tick = 5
    third_payload = manager._encoded_snapshot_bytes(loop)
    assert third_payload != b""
    assert loop.snapshot_calls == 2


@pytest.mark.asyncio
async def test_simulation_manager_closes_when_loop_missing() -> None:
    """Verifies explicit policy-close behavior when no simulation loop is loaded.

    The machine-facing stream must not emit placeholder payloads in draft-only mode. A policy close
    code communicates the live-loop precondition to clients unambiguously.
    """
    manager = SimulationStreamManager()
    websocket = _FakeWebSocket()

    await manager.handle_connection(websocket, None)

    assert websocket.accepted is True
    assert websocket.closed == [(1008, "No scenario loaded.")]


@pytest.mark.asyncio
async def test_simulation_manager_emits_final_payload_on_terminated_loop() -> None:
    """Verifies final-state emission before graceful closure at loop termination.

    When the simulation reaches its terminal state, the stream must deliver the final ecological
    snapshot exactly once before ending the connection.
    """
    manager = SimulationStreamManager()
    loop = _FakeLoop(tick=9, terminated=True)
    websocket = _FakeWebSocket()

    await manager.handle_connection(websocket, loop)

    assert websocket.accepted is True
    assert len(websocket.sent_bytes) == 1
    assert websocket.closed[-1][0] == 1000


@pytest.mark.asyncio
async def test_simulation_manager_handles_disconnect_without_propagating() -> None:
    """Verifies disconnect resilience during binary payload emission.

    The manager should absorb ``WebSocketDisconnect`` exceptions and finalize cleanup without
    surfacing transport-layer failures to the API route coroutine.
    """
    manager = SimulationStreamManager()
    loop = _FakeLoop(tick=1, terminated=False)
    websocket = _FakeWebSocket(disconnect_on_send_bytes=True)

    await manager.handle_connection(websocket, loop)

    assert websocket.accepted is True
    assert websocket.closed[-1][0] == 1000


@pytest.mark.asyncio
async def test_ui_manager_waits_for_loop_then_emits_and_handles_disconnect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verifies loop-availability polling and disconnect handling for UI stream transport.

    The UI stream must tolerate intervals with no live loop, then emit JSON payloads once a loop
    becomes available, and finally terminate cleanly on disconnect.

    Args:
        monkeypatch: Monkeypatch fixture for asyncio.sleep.
    """

    async def _instant_sleep(_delay: float) -> None:
        """Instant sleep for testing."""
        return None

    monkeypatch.setattr("phids.api.websockets.manager.asyncio.sleep", _instant_sleep)

    manager = UIStreamManager(
        payload_builder=lambda snapshot: {"tick": snapshot["tick"]},
        snapshot_extractor=lambda loop: loop.get_state_snapshot(),
    )
    loop = _FakeLoop(tick=3, terminated=False)
    websocket = _FakeWebSocket(disconnect_on_send_text=True)
    calls = {"count": 0}

    def _get_loop() -> _FakeLoop | None:
        """Return a fake loop or None based on the call count.

        Returns:
            _FakeLoop | None: The fake loop or None.
        """
        calls["count"] += 1
        if calls["count"] == 1:
            return None
        return loop

    await manager.handle_connection(websocket, _get_loop)

    assert websocket.accepted is True
    assert calls["count"] >= 2
    assert websocket.closed[-1][0] == 1000


@pytest.mark.asyncio
async def test_safe_close_helpers_absorb_runtimeerror() -> None:
    """Verifies close helper resilience when sockets are already closed upstream.

    Some ASGI stacks raise ``RuntimeError`` on duplicate close attempts. The managers treat this as
    a benign shutdown condition to preserve deterministic route completion.
    """
    failing_websocket = _FakeWebSocket(close_raises_runtime_error=True)

    await SimulationStreamManager._safe_close(failing_websocket)
    await UIStreamManager._safe_close(failing_websocket)

    assert failing_websocket.closed == []
