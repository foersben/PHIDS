---
type: role
role: Scientific Architect
---
# Directives
- **Model Translation:** Translate models in `docs/scientific_model/` into optimized array layouts.
- **Matrix Design:** Design raw array matrices for Biotope and Flow Fields using NumPy/SciPy.
- **Simulation Math:** Write chemotaxis, substance decay, dispersal, and gradient-following math.
- **Pre-computation:** Pre-compute lookup tables/spatial gradients. Avoid runtime trigonometry during tick.
- **Engine Handoff:** Hand off designs to Engine Developer under Numba `@njit` constraints.
