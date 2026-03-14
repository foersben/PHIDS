# PHIDS Project Architecture Rules
1. **Strict Data-Oriented Design:** Never use Python objects for entities. Use ECS structure.
2. **Vectorization:** Use `numpy` for all matrices. NEVER use native Python multi-dimensional lists.
3. **Double Buffering:** Logic systems must ONLY read from `State_Read` and write to `State_Write`. Never mutate the read buffer.
4. **Memory Allocation:** Obey the "Rule of 16". Pre-allocate arrays to maximum sizes of 16 (e.g., flora, predators). No dynamic `np.append` or list resizing during the simulation loop.
5. **JIT Compilation:** Use `numba.njit` for intensive loops. Ensure data types passed to numba are strictly typed (e.g., float32 over float64 for speed if applicable).
6. **Subnormal Floats:** Truncate convolution matrix tails < 1e-4 to 0.0 immediately.
7. **Spatial Queries:** Always utilize the $O(1)$ Spatial Hash; never calculate O(N^2) Euclidean distances.

## Documentation & Writing Style
When writing docstrings, comments, or markdown documentation, you MUST adhere to a rigorous,
scholarly, and scientific writing style:

1. **Explanatory Depth (Floating Texts):** Do not write terse, one-line summaries. Module and class
   docstrings must contain long, precise, and comprehensive explanatory paragraphs (floating texts)
   that detail the algorithmic mechanics AND the biological rationale.
2. **Academic Tone:** Use a formal, academic tone. Avoid colloquialisms, conversational filler
   (e.g., "basically", "just", "so"), and first-person pronouns.
3. **Domain Precision:** Strictly use the project's scientific and mathematical terminology (e.g.,
   "systemic acquired resistance", "metabolic attrition", "O(1) spatial hash lookups", "mitosis",
   "Gaussian diffusion").
4. **Structure:**
   - Start with a precise declarative sentence.
   - Follow with a detailed paragraph explaining the *why* and *how* of the system.
   - Explicitly state the relationship between the computational logic (e.g., ECS,
	 double-buffering) and the biological phenomena it simulates.
5. **Formatting:** Adhere strictly to Google-style docstrings, but expand the top-level description
   into a mini-essay or scholarly abstract.
