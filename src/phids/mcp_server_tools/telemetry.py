"""Telemetry inspection and validation MCP tools."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    import zarr


def _extract_frame_count(root: zarr.Group) -> int:
    """Extract frame count from the consolidated _metadata JSON array.

    Args:
        root: The root Zarr group representing the store.

    Returns:
        int: The number of frames, or -1 if the metadata is corrupt/missing.
    """
    import numpy as np

    frame_count: int = 0
    if "_metadata" in root:
        try:
            meta_node = cast("zarr.Array[Any]", root["_metadata"])
            meta_bytes = bytes(np.asarray(meta_node[:], dtype=np.uint8).tolist())
            meta_obj = json.loads(meta_bytes.decode("utf-8"))
            if isinstance(meta_obj, list):
                frame_count = len(meta_obj)
            elif isinstance(meta_obj, dict) and "_metadata" in meta_obj:
                inner = meta_obj["_metadata"]
                frame_count = len(inner) if isinstance(inner, list) else 0
        except Exception:  # pragma: no cover - corrupt metadata
            frame_count = -1  # Corrupt metadata - indicate uncertainty
    return frame_count


def inspect_telemetry_schema_impl(zarr_store_path: str) -> dict[str, Any]:
    """Expose Zarr replay store structure to the agent.

    Allows autonomous MLOps operators to inspect frame counts, top-level tree
    keys, and store-level metadata before initiating a heavy Polars lazy-frame
    extraction. The store is opened read-only; no data is mutated.

    Args:
        zarr_store_path: Filesystem path to a PHIDS ``.zarr`` replay store
            directory.

    Returns:
        dict[str, Any]: On success - ``status``, ``store_path``, ``frame_count``,
        ``tree_keys``, and ``store_attrs``. On failure - ``status`` and
        ``message``.
    """
    try:
        import zarr
    except ImportError as exc:  # pragma: no cover
        return {"status": "error", "message": f"Required package not available: {exc}"}

    store = Path(zarr_store_path)
    if not store.exists():
        return {
            "status": "error",
            "message": f"Store path does not exist: {zarr_store_path}",
        }

    try:
        root: zarr.Group = zarr.open_group(str(store), mode="r")
        tree_keys: list[str] = list(root.keys())

        frame_count = _extract_frame_count(root)

        store_attrs: dict[str, Any] = dict(root.attrs) if root.attrs else {}

        return {
            "status": "success",
            "store_path": str(store.resolve()),
            "frame_count": frame_count,
            "tree_keys": tree_keys,
            "store_attrs": store_attrs,
        }
    except Exception as exc:
        return {"status": "error", "message": f"Failed to read Zarr store: {exc}"}
