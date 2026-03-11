# PHIDS Project Architecture Rules
1. **Strict Data-Oriented Design:** Never use Python objects for entities. Use ECS structure.
2. **Vectorization:** Use `numpy` for all matrices. NEVER use native Python multi-dimensional lists.
3. **Double Buffering:** Logic systems must ONLY read from `State_Read` and write to `State_Write`. Never mutate the read buffer.
4. **Memory Allocation:** Obey the "Rule of 16". Pre-allocate arrays to maximum sizes of 16 (e.g., flora, predators). No dynamic `np.append` or list resizing during the simulation loop.
5. **JIT Compilation:** Use `numba.njit` for intensive loops. Ensure data types passed to numba are strictly typed (e.g., float32 over float64 for speed if applicable).
6. **Subnormal Floats:** Truncate convolution matrix tails < 1e-4 to 0.0 immediately.
7. **Spatial Queries:** Always utilize the $O(1)$ Spatial Hash; never calculate O(N^2) Euclidean distances.