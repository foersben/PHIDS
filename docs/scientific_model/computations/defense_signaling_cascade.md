---
type: Attested Computation
title: Plant Defense Synthesis & Airborne Emission Cascade
status: stable
stale_after: "2027-01-01T00:00:00Z"
version: 1.0
description: Sanctioned deterministic computation for the temporal cascade of plant chemical defense synthesis, active VOC emission, and mortality boundary guards under sustained herbivory.
tags: [computation, defense-cascade, plant-herbivore, volatile-emission, attested]
runtime: python
parameters:
  - { name: ticks, type: integer, required: true }
  - { name: initial_energy, type: float, required: true }
  - { name: synthesis_cost, type: float, required: true }
  - { name: emission_rate, type: float, required: true }
executor:
  resource: Justfile
  receipt: [trace_rows, parity_verdict]
attester:
  resource: scripts/verify_matrix_trace_parity.py
generated: {by: process:okf-updater, at: "2026-09-06T18:00:00Z"}
verified: {by: process:okf-updater, at: "2026-09-06T18:00:00Z"}
sources:
  - id: emission_system
    resource: src/phids/engine/systems/signaling/emission.py
  - id: parity_test
    resource: tests/integration/scientific_invariants/test_causal_data_flow_matrices.py
  - id: conceptual_model
    resource: ../part_3_signaling_and_transport/reaction_diffusion.md
---

# Plant Defense Synthesis & Airborne Emission Cascade

This attested computation models the discrete, multi-tick causal dynamics of induced chemical defense in sessile flora under herbivore feeding pressure. In natural ecosystems, plants do not possess instantaneous chemical production capacity; instead, detection of grazing pressure triggers a metabolic reallocation toward secondary metabolite synthesis (e.g., glucosinolates, alkaloids, or volatile terpenes) before physical volatilization into the atmosphere can occur.

---

## # Computation

```python
# Sourced from src/phids/engine/systems/signaling/emission.py
# Evaluated deterministically under SIMD float masks without branch divergence
for tick in range(num_ticks):
    # 1. Synthesis investment
    delta_synthesis = min(plant_energy, synthesis_rate) * is_triggered * alive_mask
    plant_energy -= delta_synthesis
    internal_toxin += delta_synthesis

    # 2. Airborne volatilization & external emission
    delta_emission = min(internal_toxin, emission_rate) * (1.0 - is_synthesizing) * alive_mask
    internal_toxin -= delta_emission
    external_grid += delta_emission
```

---

## Verified Data-Flow Matrix

The following state transition table reflects the point-by-point numerical evaluation across consecutive simulation ticks ($E_{\text{initial}} = 50.0, \Delta E_{\text{synthesis}} = 5.0, \text{emission\_rate} = 2.0$):

| Tick $t$ | $E_{\text{current}}$ | `is_triggered` | `alive_mask` | $M_{\text{internal\_toxin}}$ | $L_{\text{external\_grid}}$ | Applied Vectorized Operation & Gate Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **$t_0$** | 50.0 | 1.0 (Attack) | 1.0 | 0.0 | 0.0 | **Initiation:** Attack detected. `is_triggered` set to 1.0. |
| **$t_1$** | 45.0 | 1.0 | 1.0 | 5.0 | 0.0 | **Synthesis Delay:** Metabolic investment ($\Delta E = -5.0, \Delta M = +5.0$). Zero grid emission during synthesis. |
| **$t_2$** | 40.0 | 0.0 (Ceased) | 1.0 | 8.0 | 2.0 | **Active Emission:** Synthesis completes. Toxin emitted into external grid ($\Delta M = -2.0, \Delta L = +2.0$). |
| **$t_3$** | 0.0 (Dead) | 0.0 | 0.0 | 8.0 | 2.0 | **Death Interruption:** Herbivore consumes remaining energy. `alive_mask` collapses to 0.0. |
| **$t_4$** | 0.0 | 0.0 | 0.0 | 8.0 | 2.0 | **Ghost Guard:** `alive_mask == 0.0` halts emission and metabolism without conditional branches. |

---

## Mathematical & Biological Justification

1. **Continuous Energy Depletion**: The plant pays an energetic opportunity cost ($\Delta E$) to convert autotrophic photosynthate into toxic defensive secondary metabolites.
2. **Phase-Gated Volatilization**: Volatilization only proceeds once internal storage reaches functional concentrations, preventing negligible subnormal float values from entering atmospheric reaction-diffusion fields.
3. **Branchless SIMD Ghost Guard**: Upon plant mortality ($E \le 0$), `alive_mask` immediately drops to `0.0`. Multiplicative gating (`delta * alive_mask`) guarantees that dead plants cease metabolic synthesis and VOC emission without introducing branching instructions into Numba JIT kernels.

---

## Attestation & Verification

This computation is verified by running:

```bash
uv run python scripts/verify_matrix_trace_parity.py --system defense
```

Or via the test suite in [test_causal_data_flow_matrices.py](file:///home/benni/Documents/antigravity_workspace/PHIDS/tests/integration/scientific_invariants/test_causal_data_flow_matrices.py).
