# Technical Architecture Audit Report

## 1. Loop Execution Inconsistencies
The documented execution order in `engine_execution.md` is inconsistent with the actual implementation in `src/phids/engine/loop.py`.
- **Phase Counting:** The documentation lists 7 distinct phases, while the code groups them into 6 numbered phases.
- **Camouflage Attenuation:** The documentation describes Camouflage Attenuation as a separate Phase 2. In `loop.py`, it is executed as part of Phase 1 (Flow-field update).
- **Energy Layer Rebuild:** The documentation combines Telemetry and Energy Rebuild into Phase 6. In the code, `self.env.rebuild_energy_layer()` is executed immediately after Phase 4 (Signaling) and before Phase 5 (Telemetry).
- **Phase Shifting:** Because of the above differences, Telemetry is Phase 5 in the code (Phase 6 in docs), and Termination Check is Phase 6 in the code (Phase 7 in docs).

## 2. Memory/ECS Layout Hallucinations
The documentation makes several false claims regarding memory management and ECS layouts:
- **Zero-Allocation Claims:** The documentation asserts "Zero-Allocation Bootstrapping" and "Immutable Memory Allocation". However, `ECSWorld` (`ecs.py`) relies heavily on standard dynamic Python dictionaries and sets (e.g., `self._entities = {}`, `self._component_index = defaultdict(set)`), which allocate memory dynamically during the simulation. Additionally, `TelemetryRecorder` appends Python dictionaries to a list dynamically.
- **Array Structures & IO:** The documentation suggests highly optimized buffer structures, but the implementation actually uses standard 2D/3D NumPy arrays (e.g., in `biotope.py`). Furthermore, operations like `self._append_replay_frame()` in `loop.py` use synchronous IO within the hot loop rather than non-blocking async ring buffers.

## 3. Incomplete Sections
- In `interfaces_and_ui.md`, the section `### Placement Editor & Auto-Assignment` ends abruptly with just `--` and no content before transitioning to the next paragraph.

## 4. Missing UML/Mermaid Diagrams
- There is a lack of a comprehensive UML/Mermaid diagram illustrating the complex data flow pipeline from the HTMX frontend, through the DraftState mutations, into the live Engine Core (`SimulationLoop`), and finally out to the Zarr replay persistence layer and telemetry exporters.
