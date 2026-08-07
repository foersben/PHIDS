from phids.engine.core.biotope import GridEnvironment
from phids.shared.constants import GRID_W_MAX, GRID_H_MAX, MAX_SUBSTANCE_TYPES

print(f"GRID_W_MAX={GRID_W_MAX}")
print(f"GRID_H_MAX={GRID_H_MAX}")
print(f"MAX_SUBSTANCE_TYPES={MAX_SUBSTANCE_TYPES}")

try:
    env_max = GridEnvironment(
        width=GRID_W_MAX, height=GRID_H_MAX, num_signals=MAX_SUBSTANCE_TYPES, num_toxins=MAX_SUBSTANCE_TYPES
    )
    print("Success")
except Exception as e:
    print(f"Error: {e}")
