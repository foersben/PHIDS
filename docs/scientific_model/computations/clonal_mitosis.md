---
type: Attested Computation
title: Herbivore Clonal Mitosis & Biomass Bifurcation
status: stable
stale_after: "2027-01-01T00:00:00Z"
version: 1.0
description: Sanctioned deterministic computation for the 168-tick phase-staggered clonal mitosis bifurcation and biomass partitioning in foraging herbivore swarms.
tags: [computation, clonal-mitosis, population-dynamics, biomass-bifurcation, reproduction, attested]
runtime: python
parameters:
  - { name: parent_pop, type: integer, required: true }
  - { name: parent_energy, type: float, required: true }
  - { name: split_threshold, type: float, required: true }
  - { name: stride_ticks, type: integer, required: true }
executor:
  resource: Justfile
  receipt: [trace_rows, parity_verdict]
attester:
  resource: scripts/verify_matrix_trace_parity.py
generated: {by: process:okf-updater, at: "2026-09-06T18:00:00Z"}
verified: {by: process:okf-updater, at: "2026-09-06T18:00:00Z"}
sources:
  - id: reproduction_system
    resource: src/phids/engine/systems/lifecycle/reproduction.py
  - id: parity_test
    resource: tests/integration/scientific_invariants/test_causal_data_flow_matrices.py
  - id: conceptual_model
    resource: ../population_dynamics.md
---

# Herbivore Clonal Mitosis & Biomass Bifurcation

This attested computation models the macro-scale clonal splitting of herbivore swarms that have grazed dense, undefended flora and accumulated caloric reserves far exceeding individual capacity ceilings.

---

## # Computation

```python
# Sourced from src/phids/engine/systems/lifecycle/reproduction.py
# Evaluated on 168-tick slow-loop reproductive gates
if tick % 168 == 0 and parent_energy >= split_threshold and parent_pop >= 2:
    daughter_pop = parent_pop // 2
    parent_pop = parent_pop - daughter_pop
    daughter_energy = parent_energy / 2.0
    parent_energy = parent_energy / 2.0
    split_occurred = 1.0
```

---

## Verified Data-Flow Matrix

The following state transition table reflects the point-by-point numerical evaluation across a 168-tick slow-loop reproductive stride boundary ($\text{pop}_{\text{parent}} = 20 \to 10, E = 50.0 \to 25.0$):

| Tick $t$ | `parent_pop` | `parent_energy` | `daughter_pop` | `daughter_energy` | `split_occurred` | Applied Vectorized Operation & Gate Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **$t_0$** | 20 | 50.0 | 0 | 0.0 | 0.0 | **Accumulation Phase:** Swarm forages and builds caloric surplus prior to weekly check. |
| **$t_{168}$** | 10 | 25.0 | 10 | 25.0 | 1.0 | **Clonal Bifurcation:** 168-tick boundary reached; population and energy partition equally ($E_{\text{daughter}} = E/2$). |

---

## Mathematical & Biological Justification

1. **Conservation of Caloric Mass**: Clonal mitosis strictly conserves total population and energy ($E_{\text{parent}} + E_{\text{daughter}} = E_{\text{original}}$). Reproduction cannot spontaneously generate energy or organisms from nothing.
2. **Phase-Staggered Evaluation (168 Ticks)**: Heavy reproductive checks and entity allocations execute on slow weekly strides. This prevents synchronization spikes where thousands of entities attempt to split on the exact same tick.
3. **Integer Swarm Partitioning**: The swarm fractures cleanly into whole integer organisms (`parent_pop // 2`), preventing fractional population anomalies.

---

## Attestation & Verification

This computation is verified by running:

```bash
uv run python scripts/verify_matrix_trace_parity.py --system mitosis
```
