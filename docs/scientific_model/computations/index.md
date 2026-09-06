# Attested Computations Suite

This section formalizes the deterministic mathematical computations and causal Data-Flow Matrices of the PHIDS scientific model as first-class `type: Attested Computation` concepts, adhering to the Open Knowledge Format (OKF v0.2 §10) specification.

Each attested computation specifies a sanctioned execution environment (`runtime: python`), bound input parameters, execution recipe (`executor`), deterministic attestation check (`attester`), and bilateral links to the underlying engine systems and Pytest trace verification suites.

---

## Sanctioned Computations

* [Defense Signaling Cascade](defense_signaling_cascade.md) - Sanctioned computation for plant chemical defense synthesis, airborne VOC emission, and grazing mortality boundary guards.
* [Phloem Translocation](phloem_translocation.md) - Multi-tick rate-limited phloem nutrient relaxation and vascular transport kinetics.
* [Herbivore Starvation & Metabolic Attrition](herbivore_starvation.md) - 24-tick stride metabolic tax, caloric debt accumulation, and starvation attrition.
* [Mycorrhizal Propagation](mycorrhizal_propagation.md) - Underground fungal multi-hop signal propagation, metabolic upkeep tax, and instantaneous network warnings.
* [Clonal Mitosis & Biomass Bifurcation](clonal_mitosis.md) - 168-tick phase-staggered biomass and energy bifurcation under grazing abundance.

---

## Attestation Protocol

Consumers verify these computations by executing the declared `attester` (`scripts/verify_matrix_trace_parity.py` via `just verify-matrix`), confirming that runtime simulation traces achieve 1:1 point-by-point numerical parity against the documented matrices without floating-point divergence.
