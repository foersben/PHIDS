# Architecture Documentation

This document provides Mermaid.js diagrams describing the PHIDS (Plant-Herbivore Interaction &
Defense Simulator) architecture.

---

## 1. System Architecture Overview

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

---

## 2. Simulation Loop State Machine

```mermaid
stateDiagram-v2
    [*] --> Idle : Application starts

    Idle --> Loaded : POST /api/scenario/load
    Loaded --> Running : POST /api/simulation/start
    Running --> Paused : POST /api/simulation/pause
    Paused --> Running : POST /api/simulation/pause
    Running --> Terminated : Z1–Z7 condition met
    Terminated --> Loaded : POST /api/scenario/load (reload)

    state Running {
        [*] --> FlowField
        FlowField --> Lifecycle : compute_flow_field (numba)
        Lifecycle --> Interaction : grow / reproduce / cull
        Interaction --> Signaling : feed / starve / mitosis
        Signaling --> Telemetry : synthesise / diffuse / toxins
        Telemetry --> CheckTermination : record Polars row
        CheckTermination --> FlowField : not terminated
        CheckTermination --> [*] : terminated
    }
```

---

## 3. Substance Trigger Matrix – Logical Flow

```mermaid
flowchart TD
    A([Tick Start]) --> B{Predator at plant cell?<br/>via Spatial Hash O1}
    B -- No --> END([No synthesis])
    B -- Yes --> C{population ≥ n_i,min?}
    C -- No --> END
    C -- Yes --> D{Precursor signal active?}
    D -- No, required --> END
    D -- Yes / not required --> E[Start synthesis timer<br/>T_s_x ticks]
    E --> F{synthesis_remaining = 0?}
    F -- No --> G[Decrement counter]
    G --> F
    F -- Yes --> H[Substance ACTIVE]
    H --> I{is_toxin?}
    I -- Signal --> J[Emit into signal_layers<br/>Relay via mycorrhizal network<br/>SciPy convolve2d diffusion]
    I -- Toxin --> K{lethal?}
    K -- Yes --> L[Apply β casualties to swarms]
    K -- No --> M{repellent?}
    M -- Yes --> N[Set swarm.repelled = True<br/>k-tick random walk]
    M -- No --> O[Passive toxin presence]
    L --> P{Trigger still active?}
    N --> P
    O --> P
    P -- Yes --> H
    P -- No, aftereffect > 0 --> Q[Decrement T_k aftereffect]
    Q --> H
    P -- No, aftereffect = 0 --> R[Deactivate / GC substance entity]
    R --> END2([Tick End])
    J --> END2
```

---

## 4. ECS Entity Lifecycle

```mermaid
graph LR
    subgraph Spawn
        S1[create_entity] --> S2[add_component]
        S2 --> S3[register_position<br/>Spatial Hash]
    end

    subgraph Live
        L1[query components] --> L2[System logic]
        L2 --> L3[move_entity<br/>update hash]
        L3 --> L1
    end

    subgraph Death
        D1{energy < threshold?<br/>population ≤ 0?} -- Yes --> D2[unregister_position]
        D2 --> D3[collect_garbage]
    end

    S3 --> L1
    L2 --> D1
    D3 --> |entity removed| END([GC Complete])
```
