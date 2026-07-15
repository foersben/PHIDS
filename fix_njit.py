import re

with open('src/phids/engine/systems/interaction/movement.py', 'r') as f:
    text = f.read()

text = re.sub(r'(@njit\(cache=True\)\n)+def _random_walk_step_jit', r'@njit(cache=True)\ndef _random_walk_step_jit', text)
text = re.sub(r'(@njit\(cache=True\)\n)+def _choose_neighbour_by_flow_probability_jit', r'@njit(cache=True)\ndef _choose_neighbour_by_flow_probability_jit', text)

with open('src/phids/engine/systems/interaction/movement.py', 'w') as f:
    f.write(text)
