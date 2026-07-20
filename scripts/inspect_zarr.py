#!/usr/bin/env python3
"""CLI utility to inspect and validate PHIDS Zarr replay stores."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, cast

import numpy as np
import zarr


def _inspect_metadata(root: zarr.Group) -> None:
    """Inspect and print Zarr consolidated metadata."""
    if "_metadata" not in root:
        print("Warning: Consolidated '_metadata' array not found at root.", file=sys.stderr)
        return

    try:
        meta_array: Any = root["_metadata"]
        meta_bytes: bytes = bytes(np.asarray(meta_array[:], dtype=np.uint8).tolist())
        meta_obj: Any = json.loads(meta_bytes.decode("utf-8"))

        if isinstance(meta_obj, list):
            metadata_list = cast("list[dict[str, Any]]", meta_obj)
            frame_offset = 0
        else:
            metadata_list = cast("list[dict[str, Any]]", meta_obj.get("_metadata", []))
            frame_offset = int(meta_obj.get("_frame_offset", 0))

        print("Metadata Status:")
        print(f"  Consolidated Frames: {len(metadata_list)}")
        print(f"  Frame Offset Index:  {frame_offset}")
    except Exception as e:
        print(f"Error decoding consolidated metadata: {e}", file=sys.stderr)


def _inspect_frames(root: zarr.Group) -> int:
    """Inspect and print Zarr frame structure.

    Returns:
        int: Exit code (0 for success, 1 for errors).
    """
    frames_group: Any = root.get("frames")
    if frames_group is None:
        print("Error: 'frames' group not found in Zarr root.", file=sys.stderr)
        return 1

    frame_keys: list[str] = sorted(cast("list[str]", list(frames_group.keys())))
    print(f"Frame Count in Zarr Store: {len(frame_keys)}")
    if not frame_keys:
        print("No frames recorded in Zarr store.")
        return 0

    print(f"  Oldest frame: {frame_keys[0]}")
    print(f"  Newest frame: {frame_keys[-1]}")

    # Inspect first frame for array shapes and dtypes
    sample_frame_key: str = frame_keys[0]
    sample_frame: Any = frames_group[sample_frame_key]
    print(f"\nSample Frame '{sample_frame_key}' Array Structures:")
    for key in sorted(cast("list[str]", list(sample_frame.keys()))):
        node: Any = sample_frame[key]
        if isinstance(node, zarr.Array):
            print(f"  - {key:20}: shape={node.shape}, dtype={node.dtype}, chunks={node.chunks}")
        else:
            print(f"  - {key:20}: {type(node)}")

    # 3. Validate against expected fields
    expected_fields: set[str] = {
        "plant_energy_layer",
        "signal_layers",
        "toxin_layers",
        "flow_field",
        "wind_vector_x",
        "wind_vector_y",
    }
    found_fields: set[str] = set(sample_frame.keys())
    missing_fields: set[str] = expected_fields - found_fields
    if missing_fields:
        print(f"\nWarning: Missing expected arrays in frame: {missing_fields}", file=sys.stderr)
    else:
        print("\nAll expected simulation array fields are present and valid.")
    return 0


def inspect_zarr(store_path: Path) -> int:
    """Read and validate a Zarr replay store.

    Args:
        store_path: Path to the Zarr store directory.

    Returns:
        int: Exit code (0 for success, 1 for errors).
    """
    if not store_path.exists():
        print(f"Error: Store path '{store_path}' does not exist.", file=sys.stderr)
        return 1

    try:
        root: zarr.Group = zarr.open_group(str(store_path), mode="r")
    except Exception as e:
        print(f"Error opening Zarr group: {e}", file=sys.stderr)
        return 1

    print("==================================================")
    print(f"Zarr Replay Store: {store_path.resolve()}")
    print("==================================================")

    _inspect_metadata(root)
    code = _inspect_frames(root)

    print("==================================================")
    return code


def main() -> None:
    """Parse CLI arguments and run inspection."""
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description="Inspect Zarr replay buffer structures.")
    parser.add_argument("path", type=str, help="Path to the Zarr store directory")
    args: argparse.Namespace = parser.parse_args()
    sys.exit(inspect_zarr(Path(args.path)))


if __name__ == "__main__":
    main()
