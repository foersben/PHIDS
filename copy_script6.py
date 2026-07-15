with open('/tmp/interaction_orig.py', 'r') as f:
    text = f.read()

import re
match = re.search(r'(def _choose_neighbour_by_flow_probability\(.*?\n\)\s*->\s*tuple\[int,\s*int\]:.*?return [A-Za-z0-9_\(,\.\s]+\n)\n\n\ndef _random_walk_step_jit', text, re.DOTALL)

with open('src/phids/engine/systems/interaction/movement.py', 'r') as f:
    mov = f.read()

mov = re.sub(
    r'def _choose_neighbour_by_flow_probability\(.*?\n\)\s*->\s*tuple\[int,\s*int\]:.*?return _choose_neighbour_by_flow_probability_jit[A-Za-z0-9_\(,\.\s]+\n',
    match.group(1),
    mov,
    flags=re.DOTALL
)

with open('src/phids/engine/systems/interaction/movement.py', 'w') as f:
    f.write(mov)
