import numpy as np
import numpy.typing as npt

def f(x: npt.NDArray[np.float64]) -> float:
    return float(x[0,0])
