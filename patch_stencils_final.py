import re

with open('src/phids/engine/core/flow/stencils.py', 'r') as f:
    code = f.read()

old_stencil = '''@njit(cache=True)
def _init_base_and_current_jit(
    width: int,
    height: int,
    plant_energy: npt.NDArray[np.float64],
    apparent_nutrition_layer: npt.NDArray[np.float64],
    toxin_layers: npt.NDArray[np.float64],
    base: npt.NDArray[np.float64],
    current: npt.NDArray[np.float64],
    alpha: float,
    beta: float,
) -> None:
    """Initialize base and current attraction flow fields using SIMD-vectorized matrix math.

    Args:
        width: Grid width.
        height: Grid height.
        plant_energy: 2D array of plant energy per cell.
        apparent_nutrition_layer: 2D array of apparent nutrition multipliers per cell.
        toxin_layers: 3D array of toxin concentration layers per cell.
        base: Pre-allocated 2D array for base flow field.
        current: Pre-allocated 2D array for current flow field.
        alpha: Weight for botanical attractants.
        beta: Weight for toxic repellents.
    """
    num_toxins = toxin_layers.shape[0]

    for x in range(width):
        for y in range(height):
            base[x, y] = alpha * plant_energy[x, y] * apparent_nutrition_layer[x, y]

    for t in range(num_toxins):
        for x in range(width):
            for y in range(height):
                base[x, y] -= beta * toxin_layers[t, x, y]

    for x in range(width):
        for y in range(height):
            current[x, y] = base[x, y]'''

new_stencil = '''@njit(cache=True, fastmath=True)
def _init_base_and_current_jit(
    width: int,
    height: int,
    plant_energy: npt.NDArray[np.float64],
    apparent_nutrition_layer: npt.NDArray[np.float64],
    toxin_layers: npt.NDArray[np.float64],
    base: npt.NDArray[np.float64],
    current: npt.NDArray[np.float64],
    alpha: float,
    beta: float,
) -> None:
    """Initialize base and current attraction flow fields using SIMD-vectorized matrix math.

    Args:
        width: Grid width.
        height: Grid height.
        plant_energy: 2D array of plant energy per cell.
        apparent_nutrition_layer: 2D array of apparent nutrition multipliers per cell.
        toxin_layers: 3D array of toxin concentration layers per cell.
        base: Pre-allocated 2D array for base flow field.
        current: Pre-allocated 2D array for current flow field.
        alpha: Weight for botanical attractants.
        beta: Weight for toxic repellents.
    """
    num_toxins = toxin_layers.shape[0]

    for x in range(width):
        for y in range(height):
            b_val = alpha * plant_energy[x, y] * apparent_nutrition_layer[x, y]
            for t in range(num_toxins):
                b_val -= beta * toxin_layers[t, x, y]
            base[x, y] = b_val
            current[x, y] = b_val'''

code = code.replace(old_stencil, new_stencil)

old_trunc = '''@njit(cache=True, fastmath=True)
def _truncate_subnormals_jit(
    width: int,
    height: int,
    current: npt.NDArray[np.float64],
    threshold: float,
) -> None:
    """Helper function to truncate subnormal floats to exactly zero in-place.

    Args:
        width: The width of the grid environment.
        height: The height of the grid environment.
        current: The current flow field.
        threshold: Subnormal truncation threshold below which values are zeroed.
    """
    for x in range(width):
        for y in range(height):
            val = current[x, y]
            current[x, y] = 0.0 if abs(val) < threshold else val'''

new_trunc = '''@njit(cache=True, fastmath=True)
def _truncate_subnormals_jit(
    width: int,
    height: int,
    current: npt.NDArray[np.float64],
    threshold: float,
) -> None:
    """Helper function to truncate subnormal floats to exactly zero in-place.

    Args:
        width: The width of the grid environment.
        height: The height of the grid environment.
        current: The current flow field.
        threshold: Subnormal truncation threshold below which values are zeroed.
    """
    for x in range(width):
        for y in range(height):
            val = current[x, y]
            current[x, y] = 0.0 if val > -threshold and val < threshold else val'''

code = code.replace(old_trunc, new_trunc)

with open('src/phids/engine/core/flow/stencils.py', 'w') as f:
    f.write(code)
