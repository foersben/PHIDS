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
    tick_rate_hz: float = 10.0


class _FakeLoop:
    """Minimal loop surrogate exposing the stream-facing simulation contract."""

    def __init__(
        self, *, tick: int = 0, terminated: bool = False, tick_rate_hz: float = 10.0
    ) -> None:
        self.tick = tick
        self.state_revision = 0
        self.terminated = terminated
        self.running = False
        self.paused = False
        self.config = _FakeConfig(tick_rate_hz=tick_rate_hz)
        self.snapshot_calls = 0

    def get_state_snapshot(self) -> dict[str, int]:
        """Return deterministic snapshot payloads and count encoding requests."""
        self.snapshot_calls += 1
        return {"tick": self.tick}


class _FakeWebSocket:
    """Async WebSocket test double for manager-level transport tests."""

    def __init__(
        self,
        *,
        disconnect_on_send_bytes: bool = False,
        disconnect_on_send_text: bool = False,
        close_raises_runtime_error: bool = False,
    ) -> None:
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
        """Record close events or emulate close-time runtime errors."""
        if self.close_raises_runtime_error:
            raise RuntimeError("socket already closed")
        self.closed.append((code, reason))

    async def send_bytes(self, payload: bytes) -> None:
        """Record binary payloads or emulate client-initiated disconnects."""
        if self.disconnect_on_send_bytes:
            raise WebSocketDisconnect()
        self.sent_bytes.append(payload)

    async def send_text(self, payload: str) -> None:
        """Record text payloads or emulate client-initiated disconnects."""
        if self.disconnect_on_send_text:
            raise WebSocketDisconnect()
        self.sent_text.append(payload)


@pytest.mark.asyncio
async def test_simulation_manager_reuses_snapshot_cache_for_unchanged_tick() -> None:
    """Verifies msgpack+zlib cache reuse for repeated reads of one loop tick.

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


def test_ui_manager_reuses_encoded_payload_for_unchanged_signature() -> None:
    """Verify UI payload encoding is cached for unchanged loop state and refreshed on tick changes."""
    loop = _FakeLoop(tick=7)
    calls = {"count": 0}

    def _payload_builder(current_loop: _FakeLoop) -> dict[str, int]:
        calls["count"] += 1
        return {"tick": current_loop.tick}

    manager = UIStreamManager(payload_builder=_payload_builder)

    first = manager._encoded_payload(loop)
    second = manager._encoded_payload(loop)

    assert first == second
    assert calls["count"] == 1

    loop.tick = 8
    third = manager._encoded_payload(loop)
    assert third != ""
    assert calls["count"] == 2


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
    """

    async def _instant_sleep(_delay: float) -> None:
        return None

    monkeypatch.setattr("phids.api.websockets.manager.asyncio.sleep", _instant_sleep)

    manager = UIStreamManager(payload_builder=lambda loop: {"tick": loop.tick})
    loop = _FakeLoop(tick=3, terminated=False)
    websocket = _FakeWebSocket(disconnect_on_send_text=True)
    calls = {"count": 0}

    def _get_loop() -> _FakeLoop | None:
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
