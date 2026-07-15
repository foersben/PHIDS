import re
with open('/tmp/interaction_orig.py', 'r') as f:
    orig_inter = f.read()

match = re.search(r'(def _perform_mitosis\(.*?\n\)\s*->\s*SwarmComponent:.*?return [a-zA-Z_0-9]+)\n\n\ndef _python_flat_field_choice', orig_inter, re.DOTALL)

with open('src/phids/engine/systems/interaction/metabolism.py', 'r') as f:
    orig = f.read()

orig = re.sub(
    r'def _perform_mitosis\(.*?\n\)\s*->\s*SwarmComponent:.*?return [a-zA-Z_0-9]+\n',
    match.group(1) + '\n',
    orig,
    flags=re.DOTALL
)

with open('src/phids/engine/systems/interaction/metabolism.py', 'w') as f:
    f.write(orig)
