import time
import numpy as np
from numba import njit

MAX_FLORA_SPECIES = 4
width = 100
height = 100

_plant_energy_by_species_write = np.random.rand(MAX_FLORA_SPECIES, width, height)
_plant_energy_layer_write = np.zeros((width, height))

def rebuild_original():
    _plant_energy_layer_write[:] = _plant_energy_by_species_write.sum(axis=0)

@njit(cache=True)
def sum_axis0(src, dest):
    for i in range(src.shape[1]):
        for j in range(src.shape[2]):
            s = 0.0
            for k in range(src.shape[0]):
                s += src[k, i, j]
            dest[i, j] = s

def rebuild_new():
    sum_axis0(_plant_energy_by_species_write, _plant_energy_layer_write)

# Warmup
rebuild_original()
rebuild_new()

t0 = time.perf_counter()
for _ in range(1000):
    rebuild_original()
t1 = time.perf_counter()
print("Original:", t1 - t0)

t0 = time.perf_counter()
for _ in range(1000):
    rebuild_new()
t1 = time.perf_counter()
print("New:", t1 - t0)
