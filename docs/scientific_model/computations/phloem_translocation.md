---
type: Attested Computation
title: Rate-Limited Phloem Nutrient Translocation & Recovery
status: stable
stale_after: "2027-01-01T00:00:00Z"
version: 1.0
description: Sanctioned deterministic computation for rate-limited phloem nutrient translocation and post-grazing apparent nutrition recovery kinetics.
tags: [computation, phloem-translocation, nutrient-relaxation, morphological-defenses, attested]
runtime: python
parameters:
  - { name: initial_nutrition, type: float, required: true }
  - { name: target_nutrition, type: float, required: true }
  - { name: translocation_rate, type: float, required: true }
  - { name: withdrawal_duration, type: integer, required: true }
executor:
  resource: Justfile
  receipt: [trace_rows, parity_verdict]
attester:
  resource: scripts/verify_matrix_trace_parity.py
generated: {by: process:okf-updater, at: "2026-09-06T18:00:00Z"}
verified: {by: process:okf-updater, at: "2026-09-06T18:00:00Z"}
sources:
  - id: lifecycle_system
    resource: src/phids/engine/systems/signaling/lifecycle.py
  - id: parity_test
    resource: tests/integration/scientific_invariants/test_causal_data_flow_matrices.py
  - id: conceptual_model
    resource: ../morphological_defenses.md
---

# Rate-Limited Phloem Nutrient Translocation & Recovery

This attested computation models botanical nutrient translocation kinetics. When grazing pressure is detected, plants translocate valuable nitrogen and soluble carbohydrates from foliage to underground root sinks. This down-regulates the apparent nutritional factor $N(x, y)$, flattening the attractant field for foraging herbivores. When herbivory ceases, the plant slowly re-translocates nutrients to the canopy.

---

## # Computation

```python
# Sourced from src/phids/engine/systems/signaling/lifecycle.py
# Rate-limited asymptotic relaxation update per lifecycle tick
if plant.withdrawal_ticks_remaining > 0:
    plant.withdrawal_ticks_remaining -= 1
    plant.apparent_nutrition_factor += (
        plant.target_nutrition_factor - plant.apparent_nutrition_factor
    ) * plant.translocation_rate
else:
    plant.apparent_nutrition_factor += (
        1.0 - plant.apparent_nutrition_factor
    ) * plant.translocation_rate
```

---

## Verified Data-Flow Matrix

The following state transition table reflects the point-by-point numerical evaluation across consecutive simulation ticks ($N_{\text{initial}} = 0.5, N_{\text{target}} = 0.2, k_{\text{trans}} = 0.5, \tau_{\text{withdrawal}} = 2$ ticks):

| Tick $t$ | $N_{\text{apparent}}$ | $N_{\text{target}}$ | $k_{\text{trans}}$ | `withdrawal_ticks_remaining` | Applied Vectorized Operation & Gate Rule |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **$t_0$** | 0.5000000 | 0.2 | 0.5 | 2 | **Initiation:** Trigger satisfies withdrawal condition. Countdown initialized to 2. |
| **$t_1$** | 0.3500000 | 0.2 | 0.5 | 1 | **Withdrawal Phase:** $N^{t+1} = 0.5 + (0.2 - 0.5) \times 0.5 = 0.35$. Countdown decrements to 1. |
| **$t_2$** | 0.2750000 | 0.2 | 0.5 | 0 | **Target Convergence:** $N^{t+1} = 0.35 + (0.2 - 0.35) \times 0.5 = 0.275$. Countdown reaches 0. |
| **$t_3$** | 0.6375000 | 1.0 | 0.5 | 0 | **Recovery Initiation:** Countdown is 0; relaxation target reverts to 1.0 ($N^{t+1} = 0.275 + (1.0 - 0.275) \times 0.5 = 0.6375$). |
| **$t_4$** | 0.8187500 | 1.0 | 0.5 | 0 | **Recovery Phase:** $N^{t+1} = 0.6375 + (1.0 - 0.6375) \times 0.5 = 0.81875$. |
| **$t_5$** | 0.9093750 | 1.0 | 0.5 | 0 | **Asymptotic Approach:** $N^{t+1} = 0.81875 + (1.0 - 0.81875) \times 0.5 = 0.909375$. |
| **$t_6$** | 0.9546875 | 1.0 | 0.5 | 0 | **Restored Nutrition:** $N^{t+1} = 0.909375 + (1.0 - 0.909375) \times 0.5 = 0.9546875$. |

---

## Mathematical & Biological Justification

1. **Vascular Rate-Limiting**: Physical phloem sieves impose upper limits on sap velocity ($k_{\text{trans}}$). Plants cannot magically vanish their caloric content instantaneously.
2. **Exponential Relaxation**: As apparent nutrition approaches the target concentration, concentration-dependent osmosis slows the transfer rate asymptotically:
   $$\frac{dN}{dt} = -k_{\text{trans}} (N - N_{\text{target}})$$
3. **Seamless Flow-Field Coupling**: The scalar $N(x, y)$ multiplies directly into the flow-field tensor $F(x, y)$, modifying spatial foraging potentials without costly global graph searches.

---

## Attestation & Verification

This computation is verified by running:

```bash
uv run python scripts/verify_matrix_trace_parity.py --system phloem
```
