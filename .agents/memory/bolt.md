## 2024-05-18 - [Numba Convergence Early-Stopping]
Learning: Numba `@njit` accelerates Jacobi iterations inside array fields tremendously, but we still perform worst-case iteration paths if we do not add domain-aware logic. For systems like flow-field gradients propagating distance calculations, the array converges frequently well before the static iteration count (`width + height`) is hit.

Action: Even inside Numba kernels, track difference deltas on successive passes (`max_diff`) and add early-stopping mechanisms `break` once values change below epsilon (`< 1e-4`).
