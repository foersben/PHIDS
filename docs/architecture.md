# Architecture Documentation

This document provides Mermaid.js diagrams describing the PHIDS (Plant-Herbivore Interaction &
Defense Simulator) architecture.

Unlike a minimal diagram sheet, this note should be read as a compact interpretive companion to the
rendered figures. PHIDS is architected as a deterministic ecological simulator in which discrete
biological actors, continuous environmental fields, and externally visible telemetry remain separated
by explicit ownership boundaries. The purpose of the diagrams is therefore not merely illustrative.
They make visible the causal structure of the simulation: where state enters, where it is
transformed, and where it is exported as evidence.

Readers looking for the canonical narrative architecture chapter should also consult
`docs/architecture/index.md`. The present page preserves the concise diagram-centered view while now
adding the explanatory connective tissue that helps the figures read more like a methods section than
like isolated engineering sketches.

---

## 1. System Architecture Overview

The first diagram presents PHIDS as a layered system whose central coordinating element is
`SimulationLoop`. The surrounding boxes are not interchangeable services. They represent distinct
classes of responsibility: ingress and operator control in the API layer, state ownership in the
engine and ECS components, and observational export in telemetry and replay infrastructure. The most
important architectural fact visible here is that runtime control remains centralized even though
state is distributed across specialized stores.

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

Interpreted scientifically, this means that PHIDS can trace a published observation back through a
bounded path: exported telemetry arises from loop-mediated engine state, which in turn arises from
validated scenario inputs and the current ordered tick sequence. That traceability is more important
than superficial modularity, because it defines how confidently simulation outcomes can be explained.

---

## 2. Simulation Loop State Machine

The state machine clarifies that PHIDS is not an always-mutating process. It alternates between
well-defined control states and, when running, advances through a fixed intra-tick phase order. This
ordering is a core part of the model semantics. A change in phase order would not be a cosmetic
refactor; it would alter what counts as the current ecological state at each point in the run.

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
        Interaction --> Signaling : feed / upkeep / mitosis
        Signaling --> Telemetry : synthesise / relay / local toxins
        Telemetry --> CheckTermination : record Polars row
        CheckTermination --> FlowField : not terminated
        CheckTermination --> [*] : terminated
    }
```

The most important inference from this diagram is that signaling is downstream of interaction.
Plants therefore observe the ecological consequences of movement and feeding that have already
occurred during the current tick. Conversely, telemetry records the post-phase state rather than an
intermediate partial configuration. This is exactly the kind of ordering statement that should be
made explicit in simulation documentation.

---

## 3. Substance Trigger Matrix – Logical Flow

This trigger flow diagram compresses a more elaborate runtime mechanism into a single causal chain.
It shows that substance activation is not a monolithic boolean event, but a staged process involving
local threat detection, threshold checks, optional precursor or composite gating, synthesis delay,
and finally either volatile signaling or local toxin effects. The diagram is especially useful for
distinguishing between trigger presence and active defense, which are not synonymous in PHIDS.

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

The key architectural message is that chemical behavior remains rule-bound and spatially localized.
Predator presence is evaluated through the spatial hash, synthesis is attached to a specific owning
plant, and post-activation effects are governed by explicit persistence logic. In other words, the
diagram describes not merely a feature but a mechanistic chain of evidence from threat to response.

---

## 4. ECS Entity Lifecycle

The final figure abstracts the life history of any ECS entity into spawn, live mutation, and
garbage-collection phases. This is particularly important in PHIDS because ecological realism depends
on fast locality queries, but simulation stability depends equally on disciplined cleanup. The ECS is
therefore not just a storage technique; it is the formal mechanism by which entities become visible,
actable, and eventually removable from the world.

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

Taken together, the four diagrams show PHIDS as a simulation architecture in which reproducibility
depends on explicit state ownership, strict phase ordering, and bounded lifecycle transitions. That is
the level at which the documentation should be read: not as a collection of disconnected boxes and
arrows, but as an argument for why the simulator remains interpretable under change.

