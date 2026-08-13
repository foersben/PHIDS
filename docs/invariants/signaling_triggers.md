# PHIDS Signaling Trigger Invariants

## Core Mechanism

The signaling trigger mechanism governs the dynamic response of `PlantComponent`s to environmental stimuli, facilitating the active emission of secondary metabolites (`SubstanceComponent`s), either as communicative signals (VOCs) or defensive toxins. The interaction matrix couples stimuli (initiators) and condition predicates (activation conditions) to physiological responses (actions).

## The State Coupling Bug

The historical bug involved structural state coupling in the simulation loop. Previously, a `SubstanceComponent` utilized `active: bool` and `synthesis_remaining: int` to encode its lifecycle. However, this bipartite state was insufficient to disambiguate the state space during the `_apply_synthesize_action` phase.

When a trigger was met (`triggered_this_tick = True`), the engine invoked `_apply_synthesize_action`. If the substance was inactive and its synthesis countdown was depleted (`synthesis_remaining <= 0`), the logic incorrectly assumed the substance had completed its aftereffect window and needed to be "re-armed" (resetting `synthesis_remaining = synthesis_duration`).

However, this identical state vector (`active=False`, `synthesis_remaining=0`) was also valid when a substance had completed synthesis but its `activation_condition` (a secondary predicate like `substance_active`) remained unsatisfied. Consequently, substances trapped in this conditional wait-state were erroneously re-armed every tick, indefinitely postponing activation.

Additionally, `_process_single_trigger` bypassed the `activation_condition` check entirely for `SynthesizeSubstanceAction`, resulting in synthesis commencing regardless of the activation condition's satisfaction.

## Extracted Trigger Lifecyle Invariants

The rigorous testing and refactoring process identified the following core behavioral invariants that must hold true for all signaling triggers:

### 1. Initiator Sufficiency for Synthesis
Synthesis of a defensive substance or VOC *must* commence immediately upon the satisfaction of its `initiator` (e.g., `HerbivoreAttackInitiator`), irrespective of the state of its `activation_condition`. The metabolic cost of synthesis is incurred in anticipation of imminent need.

### 2. Condition Pre-requisite for Activation
An emitted `SubstanceComponent` *cannot* transition to an `active=True` state until its secondary `activation_condition` (e.g., `AllOfConditionSchema`) evaluates to `True`.

### 3. Synthesis Wait-State Stability
Once `synthesis_remaining` reaches zero, if the `initiator` is satisfied but the `activation_condition` is not, the `SubstanceComponent` must enter a stable wait-state (`synthesis_remaining = 0`, `active = False`). It must *not* re-arm or restart its synthesis duration.

### 4. Re-arming Constraint
A substance should only be re-armed (`synthesis_remaining = synthesis_duration`) if it is re-triggered after a period of dormancy. This implies it must *not* have been triggered in the immediate preceding tick (`triggered_last_tick = False`).

### 5. Threat Abort Mechanism
If the `initiator` becomes unsatisfied before the `synthesis_duration` completes (i.e., the threat leaves), the incomplete synthesis must be aborted. The component's `synthesis_remaining` is reset to `0` by the synthesis phase since `triggered_this_tick` evaluates to `False`.

### 6. Withdrawal Condition Strictness
Unlike synthesis, a `ResourceWithdrawalAction` is an instantaneous metabolic shift. It *must not* execute unless *both* the `initiator` and the `activation_condition` are fully met.

## State Decoupling Resolution

The resolution decoupled the trigger continuum by introducing `triggered_last_tick` to the `SubstanceComponent` data structure. During `_phase_index_and_clean_substances`, the runtime propagates the instantaneous boolean signal `triggered_this_tick` into `triggered_last_tick`. This provides the `_apply_synthesize_action` phase with explicit historical context, ensuring re-arming logic only fires on the leading edge of a stimulus event, protecting the conditional wait-states from corruption.

## Benchmark Validation & Impact on Existing Scenarios

When applying these invariants, we discover structural flaws in existing test scenarios such as `examples/ecosystem_equilibrium_benchmark_256x256.json`.

In the `Defense Bramble` species schema within this benchmark, the second trigger action (a resource withdrawal action upon attack by herbivore ID 0) explicitly sets `"activation_condition": null`. With the previous bug, `activation_condition` checks were bypassed for `SynthesizeSubstanceAction`, but *were* correctly evaluated for `ResourceWithdrawalAction`. However, an `activation_condition` of `null` evaluates to `True` (meaning unconditional). Thus, the withdrawal action operated as expected despite the surrounding logic being flawed.

For the `Primary Grass` species, the first trigger attempts to synthesize `substance_id: 0` using a `HerbivoreAttackInitiator` and a matching `herbivore_presence` condition. Since `SynthesizeSubstanceAction` historically ignored its condition completely due to the bug, it always fired purely based on the initiator. Now that the engine properly enforces the `activation_condition` check *after* synthesis, this trigger will correctly wait until synthesis completes and *then* re-verify the presence of herbivores before emitting. Because the `initiator` and `activation_condition` share the exact same parameters (`herbivore_presence`, id=0, count=4), the effect will be functionally identical: it will synthesize, check if herbivores are still present, and activate.

The critical difference emerges in compound defense alarm-chains (like the third trigger of `Defense Bramble`), which utilizes an `AllOf` condition containing a `substance_active` check. Previously, the synthesis duration countdown for the secondary substance would immediately begin regardless of the primary substance being active. Now, the `activation_condition` correctly acts as a gatekeeper *after* the synthesis duration elapses, and thanks to the `triggered_last_tick` fix, the synthesis countdown won't spuriously reset back to maximum just because the substance isn't active yet.
