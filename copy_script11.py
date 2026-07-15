with open('/tmp/interaction_orig.py', 'r') as f:
    orig = f.read()

import re
match = re.search(r'(def _perform_mitosis\(.*?\n\)\s*->\s*SwarmComponent:.*?\n(?=^def |\Z))', orig, re.DOTALL | re.MULTILINE)
mitosis = match.group(1)

match2 = re.search(r'(def _resolve_swarm_metabolism_and_reproduction\(.*?\n\)\s*->\s*bool:.*?\n(?=^def |\Z))', orig, re.DOTALL | re.MULTILINE)
meta = match2.group(1)

with open('src/phids/engine/systems/interaction/metabolism.py', 'r') as f:
    text = f.read()

text = re.sub(r'def _perform_mitosis\(.*?\n\)\s*->\s*SwarmComponent:.*?(?=def _resolve_swarm_metabolism_and_reproduction)', mitosis + '\n\n', text, flags=re.DOTALL)
text = re.sub(r'def _resolve_swarm_metabolism_and_reproduction\(.*?\n\)\s*->\s*bool:.*?(?=\n\n|\Z)', meta, text, flags=re.DOTALL)

with open('src/phids/engine/systems/interaction/metabolism.py', 'w') as f:
    f.write(text)
