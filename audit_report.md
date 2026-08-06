# PHIDS Codebase Audit Report: Scaling Documentation vs. Reality

## 1. Fraudulent `[Realized]` Tags (False Positives)

During the audit of `docs/roadmap.md` and `docs/scientific_model/future_prospects/`, the following highly complex architectural claims were marked as `[Realized]` but do not exist in the source codebase. They are either fabricated or were reverted without documentation updates.

*   **Branchless Capacity Masking**:
    *   **The Claim**: The documentation states that spatial capacity is enforced as a "boolean mask (`tile_biomass < max_cap`)" which is directly multiplied against the Softmax probability vector to instantly become `0.0`, specifically to avoid CPU pipeline flushes associated with Numba loop branch mispredictions.
    *   **The Reality**: The codebase (`src/phids/engine/systems/interaction/movement.py` in `_resolve_swarm_movement`) handles crowding using standard `if` conditional branches (`if tile_populations[...] > TILE_CARRYING_CAPACITY`), forcing a random walk dispersal state. No probability vector boolean masking exists.

*   **Visual Representation: The "Temporal Lens" (Zarr Replay)**:
    *   **The Claim**: The documentation asserts that Zarr implements "Meso/Macro lenses" via "Temporal Striding" (storing snapshots only every 24 or 168 ticks to reduce IOPS) and sparse matrix chunks.
    *   **The Reality**: The implementation (`src/phids/io/zarr_replay.py`) does not implement any temporal striding or subset sampling. It stores the full continuous arrays every single tick (`self._frame_count += 1`) and compresses them uniformly using Zstd without sparse subset extractions.

## 2. Undocumented Scaling Mechanics (False Negatives)

The following advanced performance optimizations exist in the `src/` directory hot-paths but are completely omitted from the "future prospects" and spatiotemporal scaling documentation.

*   **O(1) Anchoring Shortcut via Nutrition Layers**:
    *   Found in `_is_swarm_anchored` (`src/phids/engine/systems/interaction/movement.py`). The engine bypasses expensive ECS dictionary spatial queries for collision detection by directly polling the pre-computed `apparent_nutrition_layer` and `plant_energy_by_species` NumPy arrays. This allows constant-time $O(1)$ food validation.

*   **Power-of-2 Bitwise Toroidal Wrap**:
    *   Found in `_choose_neighbour_by_flow_probability_jit` (`src/phids/engine/systems/interaction/movement.py`). The engine avoids the slow scalar modulo operator `%` for boundary wrapping by dynamically evaluating if the grid is a power of 2. If true, it calls `_gather_neighbours_jit_pow2` which utilizes extremely fast bitwise masking (`width - 1`) for wrapping.

*   **ECS "Bolt Optimization" Dictionary Bypassing**:
    *   Found in `src/phids/engine/systems/interaction/__init__.py`. During the hot interaction loop, the engine bypasses the standard ECS query generator pipeline. It iterates directly over the underlying private `world._component_index` and `world._entities` mappings, relying on tight lifecycle invariants to avoid Python generator allocation overhead.

## 3. Missing Mermaid Diagrams

The documentation explicitly lacks `mermaid.js` architectural diagrams for the following key scaling strategies mentioned in the text:

*   **Temporal Lens Zarr Striding**: Missing visual pipeline diagrams of the (supposed) Micro/Meso/Macro data sampling and client-side interpolation flows.
*   **Multi-Scale Temporal Decoupling (Modulo-Gated Loop)**: Missing diagrams demonstrating the phase boundaries between the Fast (hourly), Medium (daily), and Slow (weekly) biological evaluation ticks.
