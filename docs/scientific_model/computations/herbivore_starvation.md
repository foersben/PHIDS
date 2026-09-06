---
type: Attested Computation
title: Herbivore Metabolic Tax & Starvation Attrition
status: stable
stale_after: "2027-01-01T00:00:00Z"
version: 1.0
description: Sanctioned deterministic computation for the 24-tick stride metabolic tax, caloric debt accumulation, and starvation mortality cascade.
tags: [computation, herbivore-kinematics, metabolic-tax, starvation-attrition, attested]
runtime: python
parameters:
  - { name: population, type: integer, required: true }
  - { name: energy, type: float, required: true }
  - { name: energy_min, type: float, required: true }
  - { name: upkeep_rate, type: float, required: true }
  - { name: stride_ticks, type: integer, required: true }
executor:
  resource: Justfile
  receipt: [trace_rows, parity_verdict]
attester:
  resource: scripts/verify_matrix_trace_parity.py
generated: {by: process:okf-updater, at: "2026-09-06T18:00:00Z"}
verified: {by: process:okf-updater, at: "2026-09-06T18:00:00Z"}
sources:
  - id: metabolism_system
    resource: src/phids/engine/systems/interaction/metabolism.py
  - id: parity_test
    resource: tests/integration/scientific_invariants/test_causal_data_flow_matrices.py
  - id: conceptual_model
    resource: ../herbivore_behavior.md
---

# Herbivore Metabolic Tax & Starvation Attrition

This attested computation models the daily metabolic upkeep expenditure and catastrophic starvation cascade of herbivore swarms inhabiting barren or overgrazed biotope patches.

---

## # Computation

```python
# Sourced from src/phids/engine/systems/interaction/metabolism.py
# Evaluated on 24-tick daily stride boundaries
if tick % 24 == 0:
    daily_upkeep = population * energy_min * upkeep_rate * 24
    if energy >= daily_upkeep:
        energy -= daily_upkeep
    else:
        # Starvation collapse: energy cannot cover baseline biological upkeep
        energy = 0.0
        population = 0
        alive_mask = 0.0
```

---

## Verified Data-Flow Matrix

The following state transition table reflects the point-by-point numerical evaluation across consecutive 24-tick daily stride cycles in an empty patch ($\text{pop} = 10, E_{\text{min}} = 1.0, \text{upkeep\_rate} = 0.05$, daily drain $= 10 \times 1.0 \times 0.05 \times 24 = 12.0$):

| Tick $t$ | `population` | `energy` | `energy_min` | `upkeep_drain` | `alive_mask` | Applied Vectorized Operation & Gate Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **$t_0$** | 10 | 20.0 | 1.0 | 0.0 | 1.0 | **Initial State:** Swarm occupies patch with caloric reserve above minimum threshold. |
| **$t_{24}$** | 10 | 8.0 | 1.0 | 12.0 | 1.0 | **Daily Metabolic Drain:** Stride boundary evaluates $\Delta E = -12.0$. Caloric reserve drops to 8.0. |
| **$t_{48}$** | 0 | 0.0 | 1.0 | 12.0 | 0.0 | **Starvation Collapse:** Second metabolic deduction exhausts reserve ($8.0 - 12.0 \le 0$). Swarm eradicated. |

---

## Mathematical & Biological Justification

1. **Phase-Staggered Metabolic Gate**: Evaluating basal metabolic maintenance every 24 ticks aligns with biological diurnal cycles while reducing CPU cycle consumption by $95.8\%$ compared to continuous tick-by-tick subtraction.
2. **Whole Organism Invariant**: Herbivores cannot exist as fractional entities. When collective energy reserves fail to satisfy baseline basal metabolism, the population collapses to an absolute integer zero.
3. **Ghost Guard Zeroing**: When `population == 0`, `alive_mask` is set to `0.0`, ensuring spatial hashing ignores the extinct swarm and flow-field solvers clear its sensory imprint.

---

## Attestation & Verification

This computation is verified by running:

```bash
uv run python scripts/verify_matrix_trace_parity.py --system starvation
```
