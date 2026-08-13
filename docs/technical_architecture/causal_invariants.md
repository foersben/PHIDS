# Causal Invariants in PHIDS

## The Finite State Machine

All complex entities, such as plant defenses (substances), must use explicit Numba-compatible state enumerations (FSMs) rather than implicit array-based float timers. This guarantees temporal causality and prevents cross-system behavioral clashes.

### DefenseState IntEnum

The `DefenseState` FSM strictly enforces the lifecycle of a plant defense:

1.  **IDLE (0)**: The defense is inactive and not triggered.
2.  **INITIATED (1)**: The trigger condition has been met, but metabolic investment has not yet begun.
3.  **TRIGGERED (2)**: The defense is actively triggered by external stimuli.
4.  **SYNTHESIZING (3)**: The plant is actively investing metabolic resources to synthesize the defense over a duration.
5.  **EMITTING (4)**: The defense is actively emitting signals or toxins into the environment.
6.  **COOLDOWN (5)**: The trigger is gone, and the defense is in an aftereffect/cooldown phase before returning to IDLE.

### Cross-System Behavioral Resolution

*   **Death during SYNTHESIZING**: If a plant dies while a substance is in the SYNTHESIZING state, the state transitions immediately to IDLE (or the entity is garbage-collected), and no EMITTING occurs. This resolves the violation where dead plants can synthesize toxins.
*   **Emission without Synthesis**: Emission can only occur if the state is EMITTING, which strictly requires a prior state of SYNTHESIZING (for non-zero synthesis durations) or TRIGGERED.
*   **Intent/Resolution Pattern**: State transitions must respect physical invariants. For instance, transitioning to EMITTING requires checking `plant_energy > 0`.
