import re
with open('/tmp/interaction_orig.py', 'r') as f:
    text = f.read()

match = re.search(r'(def _choose_neighbour_by_flow_probability\(.*?\n\)\s*->\s*tuple\[int, int\]:.*?\n(?=^def |\Z))', text, re.DOTALL | re.MULTILINE)

with open('src/phids/engine/systems/interaction/movement.py', 'r') as f:
    mov = f.read()

mov = re.sub(
    r'def _choose_neighbour_by_flow_probability\(.*?\n\)\s*->\s*tuple\[int, int\]:.*?\n(?=^def |\Z|\n\n@)',
    match.group(1),
    mov,
    flags=re.DOTALL | re.MULTILINE
)

with open('src/phids/engine/systems/interaction/movement.py', 'w') as f:
    f.write(mov)
