"""Connection managers for deterministic PHIDS WebSocket transport.

This module isolates asynchronous WebSocket stream orchestration from the FastAPI composition root.
The managers preserve protocol-specific invariants while reducing route-level control flow in
``phids.api.main``: the simulation stream emits msgpack+zlib binary snapshots keyed to simulation
ticks, and the UI stream emits compact JSON payloads keyed to rendered state signatures. By keeping
loop progression checks, payload encoding, sleep cadence, and disconnect handling in dedicated
classes, the runtime maintains strict draft-versus-live boundaries while exposing low-latency
observability of ecological dynamics.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import json
import logging
import zlib

import msgpack  # type: ignore[import-untyped]
from fastapi import WebSocket, WebSocketDisconnect

from phids.engine.loop import SimulationLoop

logger = logging.getLogger(__name__)


class SimulationStreamManager:
    """Manage binary simulation-state stream connections.

    The manager enforces the machine-facing stream contract for
    ``/ws/simulation/stream``: payloads are derived from ``SimulationLoop`` snapshots,
    serialized with msgpack, compressed with zlib, and sent only when the tick changes.
    A single cached compressed payload is retained per ``(loop identity, tick)`` pair to
    avoid redundant encoding work under multiple subscribers.

    Attributes:
        _cache_loop_id: Identity of the loop instance used for the current cache entry.
        _cache_tick: Tick number represented by the cached payload.
        _cache_payload: Compressed binary frame for the cached loop/tick pair.
    """

    def __init__(self) -> None:
        """Initialize cache slots for snapshot encoding reuse."""
        self._cache_loop_id = -1
        self._cache_tick = -1
        self._cache_payload = b""

    def _encoded_snapshot_bytes(self, loop: SimulationLoop) -> bytes:
        """Return cached compressed bytes for the current loop tick.

        Args:
            loop: Live simulation loop whose state snapshot is encoded.

        Returns:
            Compressed binary payload for transport.
        """
        loop_id = id(loop)
        if loop_id != self._cache_loop_id or loop.tick != self._cache_tick:
            snapshot = loop.get_state_snapshot()
            packed = msgpack.packb(snapshot, use_bin_type=True)
            self._cache_payload = zlib.compress(packed, level=1)
            self._cache_loop_id = loop_id
            self._cache_tick = loop.tick
        return self._cache_payload

    @staticmethod
    async def _safe_close(
        websocket: WebSocket, *, code: int = 1000, reason: str | None = None
    ) -> None:
        """Close a WebSocket connection without propagating shutdown exceptions.

        Args:
            websocket: Connected socket endpoint.
            code: WebSocket close code.
            reason: Optional close reason.
        """
        try:
            await websocket.close(code=code, reason=reason)
        except RuntimeError:
            return

    async def handle_connection(self, websocket: WebSocket, loop: SimulationLoop | None) -> None:
        """Handle one client connection for the binary simulation stream.

        Args:
            websocket: Accepted socket client.
            loop: Active simulation loop at connection time.

        Notes:
            The stream is intentionally rejected when no live simulation exists. This prevents
            clients from observing ambiguous placeholder transport states and keeps runtime
            semantics explicit.
        """
        await websocket.accept()
        logger.debug("WebSocket connected: /ws/simulation/stream")

        if loop is None:
            logger.warning("Closing /ws/simulation/stream because no scenario is loaded")
            await self._safe_close(websocket, code=1008, reason="No scenario loaded.")
            return

        last_tick = -1
        try:
            while True:
                if loop.terminated:
                    if loop.tick != last_tick:
                        await websocket.send_bytes(self._encoded_snapshot_bytes(loop))
                    break

                if loop.tick != last_tick:
                    await websocket.send_bytes(self._encoded_snapshot_bytes(loop))
                    last_tick = loop.tick

                await asyncio.sleep(1.0 / max(1.0, loop.config.tick_rate_hz))
        except WebSocketDisconnect:
            logger.info("WebSocket client disconnected from /ws/simulation/stream")
        finally:
            await self._safe_close(websocket)


class UIStreamManager:
    """Manage lightweight UI dashboard stream connections.

    The manager enforces rendering-oriented stream behavior for ``/ws/ui/stream``. It polls the
    active loop provider, emits JSON payloads only when a visible state signature changes, and uses
    the configured tick rate to regulate cadence. This preserves responsive visual telemetry while
    avoiding redundant frame emission during static states.

    Attributes:
        _payload_builder: Callable that assembles dashboard payload dictionaries.
    """

    def __init__(self, payload_builder: Callable[[SimulationLoop], dict[str, object]]) -> None:
        """Store dependencies required to assemble UI payloads.

        Args:
            payload_builder: Callable that builds one dashboard payload from a live loop.
        """
        self._payload_builder = payload_builder

    @staticmethod
    async def _safe_close(
        websocket: WebSocket, *, code: int = 1000, reason: str | None = None
    ) -> None:
        """Close a WebSocket connection without propagating shutdown exceptions.

        Args:
            websocket: Connected socket endpoint.
            code: WebSocket close code.
            reason: Optional close reason.
        """
        try:
            await websocket.close(code=code, reason=reason)
        except RuntimeError:
            return

    async def handle_connection(
        self,
        websocket: WebSocket,
        get_loop: Callable[[], SimulationLoop | None],
    ) -> None:
        """Handle one client connection for the UI JSON stream.

        Args:
            websocket: Accepted socket client.
            get_loop: Callable returning the currently active simulation loop.

        Notes:
            The connection remains open while no loop is loaded. This allows browser clients to
            subscribe once and begin receiving payloads immediately after a scenario is loaded.
        """
        await websocket.accept()
        logger.debug("WebSocket connected: /ws/ui/stream")

        last_state_signature: tuple[int, int, bool, bool, bool] | None = None
        try:
            while True:
                loop = get_loop()
                if loop is None:
                    await asyncio.sleep(0.5)
                    continue

                state_signature = (
                    id(loop),
                    loop.tick,
                    loop.running,
                    loop.paused,
                    loop.terminated,
                )
                if state_signature != last_state_signature:
                    payload = self._payload_builder(loop)
                    await websocket.send_text(json.dumps(payload, separators=(",", ":")))
                    last_state_signature = state_signature

                await asyncio.sleep(1.0 / max(1.0, loop.config.tick_rate_hz))
        except WebSocketDisconnect:
            logger.info("WebSocket client disconnected from /ws/ui/stream")
        finally:
            await self._safe_close(websocket)
