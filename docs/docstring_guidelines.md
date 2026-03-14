# Docstring Guidelines — Google Style

All Python docstrings in PHIDS must follow the Google Python docstring style. This
file documents the required format and examples so mkdocstrings produces clean,
consistent API documentation.

Summary
- Use triple-quoted strings (""") for all docstrings.
- Prefer short one-line summary followed by a blank line and an expanded
  description when necessary.
- Use sections: Args, Returns, Raises, Yields, Examples, and Notes where
  appropriate.
- Prefer type annotations in signatures and repeat brief type hints in the
  Args/Returns sections only when helpful for clarity.

Example: function

"""
Compute the attraction gradient for the environment.

Args:
    plant_energy (np.ndarray): 2-D array of plant energy distribution.
    toxin_layers (np.ndarray): 3-D array of toxin layers.
    width (int): Grid width.
    height (int): Grid height.

Returns:
    np.ndarray: Scalar attraction field of shape (width, height).

Raises:
    ValueError: If input shapes do not match expected dimensions.

Examples:
    >>> compute_flow_field(np.zeros((4,4)), np.zeros((1,4,4)), 4, 4)
    array([...])
"""

Example: class

"""
Manages all vectorised biotope layers for the PHIDS simulation.

Args:
    width (int): Grid width.
    height (int): Grid height.
    num_signals (int): Number of signal layers.
    num_toxins (int): Number of toxin layers.

Attributes:
    plant_energy_layer (np.ndarray): Aggregated energy per cell.
    signal_layers (np.ndarray): Active signal layers.
"""

Enforcement
- `pydocstyle` is configured in `pyproject.toml` and runs in pre-commit/CI.
- Use `--convention=google` with pydocstyle.

Notes
- mkdocstrings will render these docstrings in the API reference automatically.

## Scientific & Scholarly Tone Requirement

All documentation must be written in an academic, scientifically rigorous style. We prefer long,
precise explanatory texts over brief summaries.

### ❌ Bad Example (Too terse, informal)
"""Handles swarm movement and eating.
This runs every tick to make sure swarms move towards food and eat it if they are hungry.
"""

### ✅ Good Example (Scholarly, precise, comprehensive)
"""Interaction system: swarm movement, feeding, energy economy, and toxin effects.

This module implements the core behavioral loop for herbivore swarms. It governs
spatial navigation via probabilistic evaluation of the flow-field gradient,
allowing swarms to traverse the biotope towards high-energy flora while evading
localized toxin concentrations.

Furthermore, this system models the metabolic attrition of the swarm. It applies
a continuous energy deficit based on the population size and executes feeding
behavior via O(1) spatial hash co-occupancy checks. When a swarm's accumulated
energy surpasses the biological threshold, the system triggers mitosis, splitting
the population to simulate offspring generation.
"""

