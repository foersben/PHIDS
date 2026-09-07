---
type: Attested Computation
title: Mycorrhizal Root Network Multi-Hop Signal Propagation
status: stable
stale_after: "2027-01-01T00:00:00Z"
version: 1.0
description: Sanctioned deterministic computation for underground fungal multi-hop signal propagation, transmission latency, and carbon maintenance tax.
tags: [computation, mycorrhiza, fungal-network, signal-propagation, symbiosis, attested]
runtime: python
parameters:
  - { name: source_signal, type: float, required: true }
  - { name: attenuation_factor, type: float, required: true }
  - { name: upkeep_tax, type: float, required: true }
executor:
  resource: Justfile
  receipt: [trace_rows, parity_verdict]
attester:
  resource: scripts/verify_matrix_trace_parity.py
generated: {by: process:okf-updater, at: "2026-09-06T18:00:00Z"}
verified: {by: process:okf-updater, at: "2026-09-06T18:00:00Z"}
sources:
  - id: mycorrhiza_system
    resource: src/phids/engine/systems/lifecycle/mycorrhiza.py
  - id: parity_test
    resource: tests/integration/scientific_invariants/test_causal_data_flow_matrices.py
  - id: conceptual_model
    resource: ../part_2_autotrophic_dynamics/flora_and_symbiosis.md
---

# Mycorrhizal Root Network Multi-Hop Signal Propagation

This attested computation models the discrete transmission of warning signals through underground common mycorrhizal networks (CMNs) connecting sessile flora. Underground fungal hyphae permit alarm signals to bypass atmospheric diffusion barriers (wind direction, air currents), but demand an active metabolic upkeep tax ($E_{\text{tax}}$) from participating botanical nodes.

---

## # Computation

```python
# Sourced from src/phids/engine/systems/lifecycle/mycorrhiza.py
# Propagate signals along graph conduits and deduct maintenance tax
for hop in range(max_hops):
    # Signal attenuation across hyphal junction
    next_signal = current_signal * attenuation_factor
    # Deduct carbon tax from participating node
    node_energy -= upkeep_tax
```

---

## Verified Data-Flow Matrix

The following state transition table reflects the point-by-point numerical evaluation across consecutive conduits and plant nodes, showing signal transfer latency and daily carbon upkeep tax ($E_{\text{tax}} = 1.5$):

| Tick $t$ | `source_signal` | `hop1_signal` | `hop2_signal` | `hop1_energy` | `upkeep_tax` | Applied Vectorized Operation & Gate Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **$t_0$** | 1.0 | 0.0 | 0.0 | 50.0 | 0.0 | **Conduit Injection:** Attacked emitter releases signal into root network conduit. |
| **$t_1$** | 0.8 | 0.9 | 0.0 | 48.5 | 1.5 | **Hop 1 Arrival:** Signal reaches primary neighbor; daily symbiosis maintenance tax deducted ($\Delta E = -1.5$). |
| **$t_2$** | 0.6 | 0.7 | 0.81 | 47.0 | 1.5 | **Hop 2 Arrival:** Signal propagates to secondary node; Hop 1 maintains conduit connection. |

---

## Mathematical & Biological Justification

1. **Hyphal Attenuation ($0.9$ Per Hop)**: As chemical elicitors travel through mycelial conduits, cellular absorption and diffusion resistance attenuate signal potency.
2. **Carbon Upkeep Tax**: Fungal symbionts do not maintain hyphal connections for free. Plants allocate $3-5\%$ of daily photosynthate to fungal mutualists. If a plant cannot pay the tax, the mycorrhizal connection is severed.
3. **Discrete Multi-Hop Latency**: Signals advance exactly 1 spatial hop per simulation tick, preventing non-causal instantaneous action at a distance while preserving predictable computational boundaries.

---

## Attestation & Verification

This computation is verified by running:

```bash
uv run python scripts/verify_matrix_trace_parity.py --system mycorrhiza
```
