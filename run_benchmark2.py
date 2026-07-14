import time
import numpy as np

layer = np.zeros((100, 100))
sparse_grid = {(x, y): 1.5 for x in range(10, 90) for y in range(10, 90)}

def rebuild_original():
    layer.fill(0.0)
    coords = list(sparse_grid.keys())
    x_coords = [c[0] for c in coords]
    y_coords = [c[1] for c in coords]
    energies = list(sparse_grid.values())
    layer[x_coords, y_coords] += energies

def rebuild_new():
    layer.fill(0.0)
    for (x, y), energy in sparse_grid.items():
        layer[x, y] += energy

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
