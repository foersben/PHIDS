# System Architecture

The PHIDS simulator is engineered as a headless, high-performance data-oriented system. It segregates logic from state to bypass the bottlenecks inherent in traditional Object-Oriented simulation frameworks. This document outlines the fundamental technical boundaries that ensure deterministic, reproducible simulation loops.

## Runtime Center of Gravity

The architectural nexus of the project is the `SimulationLoop` (`src/phids/engine/loop.py`). It coordinates the following independent stateful subsystems:

- **`GridEnvironment`**: Manages all vectorized 2D cellular automata fields using pre-allocated NumPy arrays.
- **`ECSWorld`**: Maintains the discrete biological entities and manages spatial locality indexing.
- **`TelemetryRecorder` & `ReplayBuffer`**: Handle data serialization and analytics observation at the conclusion of every tick.

## Layered Decomposition

1. **Schema & Ingress Layer**: Uses `pydantic` to enforce experimental bounds. Scenarios must be validated before the system initializes.
2. **Runtime Engine Layer**: A strict, unvarying sequence of phase operators.
3. **Interface Layer**: FastAPI provides asynchronous REST endpoints, WebSocket streaming, and manages the HTML presentation of `DraftState` versus live configurations.
4. **Persistence Layer**: Converts real-time system state into exported Polars DataFrames and binary `msgpack` logs for reproducibility.

## Double-Buffering Mechanics

To preclude race conditions during state mutation, PHIDS implements rigorous double-buffering for specific continuous fields (e.g., signal diffusion layers and plant energy arrays).
When a system phase computes new values, it reads from the read-buffer (`State_Read`) and commits its mutations entirely to a write-buffer (`State_Write`). Only upon the conclusion of the phase are the buffer references swapped.

## Memory Bounding: The "Rule of 16"

Dynamic memory allocation during the hot simulation loop introduces prohibitive latency. The architecture imposes a strict upper bound constraint: the system accommodates a maximum of 16 distinct flora species, 16 herbivore species, and 16 substance mechanisms. Matrices (such as diet compatibility or trigger relationships) are pre-allocated at a fixed $(16 \times 16)$ scale during bootstrapping.

```mermaid
graph TD
    subgraph API["FastAPI Layer"]
        A1[POST /api/scenario/load]
        A2[POST /api/simulation/start]
        A3[POST /api/simulation/pause]
        A4[GET  /api/simulation/status]
        A5[PUT  /api/simulation/wind]
        A6[WS   /ws/simulation/stream]
        A7[GET  /api/telemetry/export/csv]
        A8[GET  /api/telemetry/export/json]
    end

    subgraph Engine["Simulation Engine"]
        L[SimulationLoop<br/>loop.py]
        BIO[GridEnvironment<br/>biotope.py]
        ECS[ECSWorld<br/>ecs.py]
        FF[FlowField<br/>flow_field.py @njit]
        LC[LifecycleSystem<br/>lifecycle.py]
        INT[InteractionSystem<br/>interaction.py]
        SIG[SignalingSystem<br/>signaling.py]
    end

    subgraph Components["ECS Components"]
        PC[PlantComponent]
        SC[SwarmComponent]
        SUB[SubstanceComponent]
    end

    subgraph Telemetry["Telemetry"]
        AN[TelemetryRecorder<br/>analytics.py]
        COND[TerminationChecker<br/>conditions.py]
        EXP[Export<br/>export.py]
    end

    subgraph IO["I/O"]
        SCN[scenario.py<br/>Pydantic load/save]
        REP[ReplayBuffer<br/>replay.py msgpack]
    end

    A1 -->|SimulationConfig| L
    A2 --> L
    A3 --> L
    A4 --> L
    A5 -->|WindUpdatePayload| BIO
    A6 -->|binary msgpack frames| REP
    A7 & A8 --> EXP

    L --> BIO
    L --> ECS
    L --> FF
    L --> LC
    L --> INT
    L --> SIG
    L --> AN
    L --> COND

    ECS --> PC
    ECS --> SC
    ECS --> SUB

    LC --> PC
    INT --> SC
    INT --> PC
    SIG --> SUB
    SIG --> BIO

    AN --> EXP
    SCN -->|SimulationConfig| L
```
