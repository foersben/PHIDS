# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Type definitions, slice views, and no-op buffers for simulation replay storage.

Provides protocols, typed dictionaries, immutable zero-copy slice abstractions,
and no-op buffer fallbacks for headless benchmarks and replay operations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, TypedDict

if TYPE_CHECKING:
    import numpy as np

type ReplayScalar = bool | int | float | str | None
type ReplayValue = ReplayScalar | list["ReplayValue"] | dict[str, "ReplayValue"]
type ReplayState = dict[str, ReplayValue]


class _ReplayEnvLike(Protocol):
    """Structural contract for environment layers consumed by append_raw_arrays."""

    plant_energy_layer: np.ndarray
    structural_mass_layer: np.ndarray
    signal_layers: np.ndarray
    toxin_layers: np.ndarray
    flow_field: np.ndarray
    wind_vector_x: np.ndarray
    wind_vector_y: np.ndarray


class _MetadataEntry(TypedDict):
    """Per-frame metadata record persisted alongside Zarr field arrays."""

    tick: int
    terminated: bool
    termination_reason: str | None


class ReplaySlice:
    """Immutable zero-copy view over a temporal slice of Zarr replay frames.

    Provides high-performance NumPy array access across consecutive simulation ticks
    without materializing Python list objects or triggering unnecessary copies.
    """

    def __init__(
        self,
        start_tick: int,
        end_tick: int,
        metadata: list[_MetadataEntry],
        fields: dict[str, np.ndarray],
    ) -> None:
        """Initialize the ReplaySlice.

        Args:
            start_tick: Start index of the slice (inclusive, 0-based).
            end_tick: End index of the slice (exclusive, 0-based).
            metadata: Metadata records for the frames in the slice.
            fields: Dictionary mapping field names to stacked or indexed NumPy arrays.
        """
        self.start_tick = start_tick
        self.end_tick = end_tick
        self.metadata = metadata
        self.fields = fields

    def __len__(self) -> int:
        """Return the number of frames contained in this slice.

        Returns:
            int: Number of frames in slice.
        """
        return len(self.metadata)

    def get_field(self, field_name: str) -> np.ndarray:
        """Retrieve the zero-copy NumPy array for a specific field in this slice.

        Args:
            field_name: Name of the environment layer field.

        Returns:
            np.ndarray: The requested field data array.

        Raises:
            KeyError: If the field is not present in this slice.
        """
        if field_name not in self.fields:
            raise KeyError(f"Field '{field_name}' not found in ReplaySlice.")
        return self.fields[field_name]

    def to_dict(self) -> dict[str, Any]:
        """Convert metadata and field arrays to a dictionary representation.

        Returns:
            dict[str, Any]: Mapping of metadata and NumPy array fields.
        """
        return {
            "start_tick": self.start_tick,
            "end_tick": self.end_tick,
            "metadata": list(self.metadata),
            "fields": self.fields,
        }


class NoOpReplayBuffer:
    """A no-op replay buffer that does not store or write frames, preventing disk usage during tuning."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the NoOpReplayBuffer (does nothing).

        Args:
            *args: Positional arguments (ignored).
            **kwargs: Keyword arguments (ignored).
        """
        pass

    def append(self, state: object) -> None:
        """Append a state snapshot to the buffer (no-op).

        Args:
            state: The simulation state object to append.
        """
        pass

    def append_raw_arrays(self, *args: Any, **kwargs: Any) -> None:
        """Append raw environment arrays to the buffer (no-op).

        Args:
            *args: Positional arguments (ignored).
            **kwargs: Keyword arguments (ignored).
        """
        pass

    def __len__(self) -> int:
        """Return the number of frames in the buffer (always 0).

        Returns:
            int: Frame count (always 0).
        """
        return 0

    def get_frame_arrays(self, tick: int) -> dict[str, np.ndarray]:
        """Return raw NumPy arrays for the frame (no-op).

        Args:
            tick: Index of the frame.

        Raises:
            IndexError: Always raised since the no-op buffer holds no frames.
        """
        raise IndexError(f"Replay frame index out of range: {tick} (buffer is empty)")

    def get_slice(self, start_tick: int, end_tick: int) -> ReplaySlice:
        """Return a ReplaySlice for the specified range (no-op).

        Args:
            start_tick: Start index.
            end_tick: End index.

        Returns:
            ReplaySlice: Empty slice container.
        """
        return ReplaySlice(
            start_tick=start_tick,
            end_tick=end_tick,
            metadata=[],
            fields={},
        )


__all__ = [
    "NoOpReplayBuffer",
    "ReplayScalar",
    "ReplaySlice",
    "ReplayState",
    "ReplayValue",
    "_MetadataEntry",
    "_ReplayEnvLike",
]
